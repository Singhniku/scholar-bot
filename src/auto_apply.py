"""
LinkedIn Easy Apply automation.

Flow:
  1. Log in to LinkedIn (stores cookies for re-use).
  2. Navigate to a job's Easy Apply page.
  3. Auto-fill every form step using resume_data.
  4. Take a screenshot of the final review page.
  5. Wait for a human "Submit" signal (threading.Event).
  6. Submit or discard based on signal value.

The class is designed to be driven from a Streamlit thread:
  - status updates are pushed to a shared dict the UI can poll.
  - screenshots are base64-encoded PNGs the UI can render with st.image.
"""
import base64
import io
import logging
import os
import re
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# -─ Selenium imports (lazy so the rest of the app works without a browser) ───
try:
    from selenium import webdriver
    from selenium.common.exceptions import (
        ElementNotInteractableException,
        NoSuchElementException,
        TimeoutException,
        StaleElementReferenceException,
    )
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait, Select
    from webdriver_manager.chrome import ChromeDriverManager

    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False


# ─── Selectors (LinkedIn HTML changes periodically — update here if needed) ──
_SEL = {
    "easy_apply_btn": "button.jobs-apply-button, button[aria-label*='Easy Apply']",
    "modal": "div.jobs-easy-apply-modal, div[data-test-modal]",
    "next_btn": "button[aria-label='Continue to next step'], button[aria-label='Review your application']",
    "submit_btn": "button[aria-label='Submit application']",
    "close_btn": "button[aria-label='Dismiss']",
    "phone_input": "input[id*='phoneNumber'], input[name*='phone']",
    "city_input": "input[id*='city'], input[aria-label*='City']",
    "linkedin_url_input": "input[id*='linkedInUrl'], input[aria-label*='LinkedIn']",
    "website_input": "input[id*='website'], input[aria-label*='Website']",
    "resume_upload": "input[type='file']",
    "text_inputs": "input[type='text']:not([disabled]), input[type='email']:not([disabled])",
    "textarea": "textarea:not([disabled])",
    "radio_yes": "label[for*='yes'], input[value='Yes']",
    "select_el": "select:not([disabled])",
    "error_msg": "span[data-test-form-element-validation-error]",
}

# LinkedIn login URLs
_LOGIN_URL = "https://www.linkedin.com/login"
_JOBS_BASE = "https://www.linkedin.com/jobs/view/{job_id}/"


class ApplicationStatus:
    IDLE = "idle"
    LOGGING_IN = "logging_in"
    NAVIGATING = "navigating"
    FILLING = "filling"
    REVIEWING = "reviewing"
    WAITING_APPROVAL = "waiting_approval"
    SUBMITTING = "submitting"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


class AutoApply:
    """
    Drives LinkedIn Easy Apply for a list of jobs.
    Designed to run in a background thread with Streamlit polling `status_dict`.
    """

    def __init__(
        self,
        email: str,
        password: str,
        resume_data: dict[str, Any],
        resume_pdf_path: str,
        headless: bool = False,
        on_status: Optional[Callable[[str, str, Optional[str]], None]] = None,
    ):
        """
        Parameters
        ----------
        email, password   : LinkedIn credentials
        resume_data       : structured resume dict (from SkillsExtractor)
        resume_pdf_path   : absolute path to the ATS-optimised PDF to upload
        headless          : run Chrome in background (screenshot-only review)
        on_status(job_id, status, screenshot_b64)
                          : callback fired on state changes; screenshot is
                            base64-encoded PNG or None
        """
        if not SELENIUM_AVAILABLE:
            raise RuntimeError(
                "selenium and webdriver-manager are required: "
                "pip install selenium webdriver-manager"
            )

        self.email = email
        self.password = password
        self.resume_data = resume_data
        self.resume_pdf_path = resume_pdf_path
        self.headless = headless
        self.on_status = on_status or (lambda *_: None)

        self._driver: Optional[webdriver.Chrome] = None
        self._submit_event: Optional[threading.Event] = None
        self._approve: bool = False

    # ── Public API ──────────────────────────────────────────────────────────

    def apply_to_jobs(self, jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Apply to a list of jobs.  Each job dict must have at least `job_id` or `url`.
        Returns list of result dicts: {job_id, title, company, status, error}.
        """
        results = []
        try:
            self._start_driver()
            self._login()

            for job in jobs:
                result = self._apply_single(job)
                results.append(result)

        except Exception as e:
            logger.error(f"Fatal error in auto-apply: {e}")
        finally:
            self._quit_driver()

        return results

    def signal_submit(self, approve: bool):
        """Call from the UI thread to approve or reject the current application."""
        self._approve = approve
        if self._submit_event:
            self._submit_event.set()

    # ── Driver setup ────────────────────────────────────────────────────────

    def _start_driver(self):
        opts = ChromeOptions()
        if self.headless:
            opts.add_argument("--headless=new")
        opts.add_argument("--window-size=1400,900")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")

        service = ChromeService(ChromeDriverManager().install())
        self._driver = webdriver.Chrome(service=service, options=opts)
        self._driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        logger.info("Chrome started")

    def _quit_driver(self):
        if self._driver:
            try:
                self._driver.quit()
            except Exception:
                pass
            self._driver = None

    def _wait(self, timeout: int = 10) -> WebDriverWait:
        return WebDriverWait(self._driver, timeout)

    def _screenshot_b64(self) -> str:
        try:
            return base64.b64encode(self._driver.get_screenshot_as_png()).decode()
        except Exception:
            return ""

    # ── Login ────────────────────────────────────────────────────────────────

    def _login(self):
        self.on_status("__global__", ApplicationStatus.LOGGING_IN, None)
        self._driver.get(_LOGIN_URL)
        time.sleep(2)

        try:
            email_el = self._wait(10).until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            email_el.clear()
            email_el.send_keys(self.email)

            pwd_el = self._driver.find_element(By.ID, "password")
            pwd_el.clear()
            pwd_el.send_keys(self.password)
            pwd_el.send_keys(Keys.RETURN)

            # Wait for redirect away from login page
            self._wait(20).until(EC.url_changes(_LOGIN_URL))
            time.sleep(2)
            logger.info("Logged in to LinkedIn")
        except TimeoutException:
            raise RuntimeError(
                "LinkedIn login failed — check credentials or solve CAPTCHA manually."
            )

    # ── Single job application ───────────────────────────────────────────────

    def _apply_single(self, job: dict[str, Any]) -> dict[str, Any]:
        job_id = job.get("job_id") or ""
        url = job.get("url") or (
            _JOBS_BASE.format(job_id=job_id) if job_id else None
        )
        title = job.get("title", "Unknown")
        company = job.get("company", "Unknown")
        result_base = {"job_id": job_id, "title": title, "company": company}

        if not url:
            return {**result_base, "status": ApplicationStatus.SKIPPED, "error": "No URL"}

        self.on_status(job_id, ApplicationStatus.NAVIGATING, None)
        try:
            self._driver.get(url)
            time.sleep(3)

            # Click Easy Apply
            try:
                easy_apply = self._wait(8).until(
                    EC.element_to_be_clickable(
                        (By.CSS_SELECTOR, _SEL["easy_apply_btn"])
                    )
                )
                easy_apply.click()
                time.sleep(2)
            except TimeoutException:
                return {
                    **result_base,
                    "status": ApplicationStatus.SKIPPED,
                    "error": "No Easy Apply button",
                }

            # Fill multi-step form
            self.on_status(job_id, ApplicationStatus.FILLING, None)
            self._fill_application_form(job)

            # Show review screenshot and wait for human approval
            screenshot = self._screenshot_b64()
            self.on_status(job_id, ApplicationStatus.WAITING_APPROVAL, screenshot)

            self._submit_event = threading.Event()
            self._approve = False
            self._submit_event.wait(timeout=300)  # 5-minute window

            if not self._approve:
                # Dismiss the modal
                try:
                    self._driver.find_element(
                        By.CSS_SELECTOR, _SEL["close_btn"]
                    ).click()
                except Exception:
                    pass
                return {
                    **result_base,
                    "status": ApplicationStatus.SKIPPED,
                    "error": "User skipped",
                }

            # Submit
            self.on_status(job_id, ApplicationStatus.SUBMITTING, None)
            try:
                submit_btn = self._wait(10).until(
                    EC.element_to_be_clickable(
                        (By.CSS_SELECTOR, _SEL["submit_btn"])
                    )
                )
                submit_btn.click()
                time.sleep(3)
                logger.info(f"Applied to {title} @ {company}")
                self.on_status(job_id, ApplicationStatus.DONE, self._screenshot_b64())
                return {**result_base, "status": ApplicationStatus.DONE}
            except TimeoutException:
                # Sometimes "Review" button leads to submit on next click
                try:
                    self._click_next()
                    time.sleep(2)
                    submit_btn = self._wait(5).until(
                        EC.element_to_be_clickable(
                            (By.CSS_SELECTOR, _SEL["submit_btn"])
                        )
                    )
                    submit_btn.click()
                    time.sleep(3)
                    return {**result_base, "status": ApplicationStatus.DONE}
                except Exception as e2:
                    return {
                        **result_base,
                        "status": ApplicationStatus.FAILED,
                        "error": f"Submit failed: {e2}",
                    }

        except Exception as e:
            logger.error(f"Error applying to {title}: {e}")
            return {**result_base, "status": ApplicationStatus.FAILED, "error": str(e)}

    # ── Form filling ─────────────────────────────────────────────────────────

    def _fill_application_form(self, job: dict[str, Any]):
        """Iterate through Easy Apply steps, filling fields on each page."""
        max_steps = 10
        for step in range(max_steps):
            self._fill_current_step()
            time.sleep(1)

            # Check for submit button (last step)
            try:
                self._driver.find_element(By.CSS_SELECTOR, _SEL["submit_btn"])
                break  # Reached review/submit step
            except NoSuchElementException:
                pass

            # Try clicking "Next" or "Review"
            if not self._click_next():
                break

            time.sleep(2)

    def _fill_current_step(self):
        """Fill all visible form fields in the current modal step."""
        rd = self.resume_data

        # Upload resume PDF if file input is present and empty
        try:
            file_inputs = self._driver.find_elements(By.CSS_SELECTOR, _SEL["resume_upload"])
            for fi in file_inputs:
                if fi.is_displayed() and self.resume_pdf_path:
                    fi.send_keys(str(Path(self.resume_pdf_path).resolve()))
                    time.sleep(2)
                    break
        except Exception:
            pass

        # Phone number
        self._fill_by_selector(_SEL["phone_input"], rd.get("phone", ""))

        # Fill labelled text inputs intelligently
        try:
            inputs = self._driver.find_elements(By.CSS_SELECTOR, _SEL["text_inputs"])
            for inp in inputs:
                if not inp.is_displayed():
                    continue
                label = self._get_label(inp).lower()
                value = self._infer_value(label, rd)
                if value and not inp.get_attribute("value"):
                    self._safe_fill(inp, value)
        except Exception as e:
            logger.debug(f"Text fill error: {e}")

        # Textareas (cover letter, additional info)
        try:
            textareas = self._driver.find_elements(By.CSS_SELECTOR, _SEL["textarea"])
            for ta in textareas:
                if ta.is_displayed() and not ta.get_attribute("value"):
                    label = self._get_label(ta).lower()
                    if "cover" in label or "additional" in label or "summary" in label:
                        self._safe_fill(ta, rd.get("summary", ""))
        except Exception:
            pass

        # Selects (dropdowns)
        try:
            selects = self._driver.find_elements(By.CSS_SELECTOR, _SEL["select_el"])
            for sel in selects:
                if sel.is_displayed():
                    self._fill_select(sel, rd)
        except Exception:
            pass

        # Radio buttons — prefer "Yes" for work authorization / sponsorship questions
        try:
            for radio in self._driver.find_elements(
                By.CSS_SELECTOR, "fieldset input[type='radio']"
            ):
                container = radio.find_element(By.XPATH, "./ancestor::fieldset[1]")
                question = container.text.lower()
                if any(
                    kw in question
                    for kw in ("authorized", "legally", "citizen", "eligible")
                ):
                    yes_label = container.find_element(
                        By.XPATH, ".//label[contains(translate(text(),'YES','yes'),'yes')]"
                    )
                    yes_label.click()
                elif "sponsor" in question:
                    no_label = container.find_element(
                        By.XPATH, ".//label[contains(translate(text(),'NO','no'),'no')]"
                    )
                    no_label.click()
        except Exception:
            pass

    def _click_next(self) -> bool:
        for selector in (
            "button[aria-label='Continue to next step']",
            "button[aria-label='Review your application']",
            "button[aria-label='Next']",
        ):
            try:
                btn = self._driver.find_element(By.CSS_SELECTOR, selector)
                if btn.is_displayed() and btn.is_enabled():
                    btn.click()
                    return True
            except NoSuchElementException:
                pass
        return False

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _fill_by_selector(self, selector: str, value: str):
        if not value:
            return
        try:
            el = self._driver.find_element(By.CSS_SELECTOR, selector)
            if el.is_displayed() and not el.get_attribute("value"):
                self._safe_fill(el, value)
        except NoSuchElementException:
            pass

    @staticmethod
    def _safe_fill(el, value: str):
        try:
            el.click()
            el.clear()
            el.send_keys(str(value))
        except Exception:
            pass

    def _get_label(self, el) -> str:
        """Return the associated label text for a form element."""
        try:
            el_id = el.get_attribute("id")
            if el_id:
                label = self._driver.find_element(By.CSS_SELECTOR, f"label[for='{el_id}']")
                return label.text
        except Exception:
            pass
        try:
            return el.find_element(By.XPATH, "./ancestor::div[1]/label").text
        except Exception:
            pass
        return el.get_attribute("placeholder") or el.get_attribute("aria-label") or ""

    @staticmethod
    def _infer_value(label: str, rd: dict[str, Any]) -> str:
        """Map a field label to a resume value."""
        mapping = {
            "phone": rd.get("phone", ""),
            "mobile": rd.get("phone", ""),
            "email": rd.get("email", ""),
            "first name": (rd.get("name", "") or "").split()[0] if rd.get("name") else "",
            "last name": " ".join((rd.get("name", "") or "").split()[1:]),
            "full name": rd.get("name", ""),
            "name": rd.get("name", ""),
            "city": (rd.get("location", "") or "").split(",")[0].strip(),
            "location": rd.get("location", ""),
            "address": rd.get("location", ""),
            "linkedin": "",
            "website": "",
            "years of experience": str(rd.get("experience_years", "")),
            "experience": str(rd.get("experience_years", "")),
            "current title": rd.get("current_title", ""),
            "current company": (
                rd.get("experience", [{}])[0].get("company", "") if rd.get("experience") else ""
            ),
            "summary": rd.get("summary", ""),
        }
        for key, val in mapping.items():
            if key in label:
                return val
        return ""

    def _fill_select(self, sel_el, rd: dict[str, Any]):
        try:
            sel = Select(sel_el)
            options = [o.text.lower() for o in sel.options]
            label = self._get_label(sel_el).lower()

            # Work authorization
            if "authorized" in label or "work" in label:
                for opt in ("yes", "i am authorized", "authorized to work"):
                    if any(opt in o for o in options):
                        sel.select_by_visible_text(
                            next(o for o in sel.options if opt in o.text.lower()).text
                        )
                        return

            # Experience years
            exp = rd.get("experience_years", 0)
            if "experience" in label or "year" in label:
                for opt in sel.options:
                    try:
                        nums = re.findall(r"\d+", opt.text)
                        if nums and int(nums[0]) <= int(exp or 0):
                            sel.select_by_visible_text(opt.text)
                    except Exception:
                        pass
        except Exception:
            pass
