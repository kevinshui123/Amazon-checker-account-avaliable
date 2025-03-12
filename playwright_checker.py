import os
import tempfile
import random
import time
from typing import List, Optional

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

PROXIES = []
REQUESTS_PER_PROXY = 5
current_proxy_index = 0
current_proxy_request_count = 0


def set_proxies(proxy_list: List[str]):
    global PROXIES, current_proxy_index, current_proxy_request_count
    PROXIES = proxy_list
    current_proxy_index = 0
    current_proxy_request_count = 0
    print(f"Proxy list updated. Total {len(PROXIES)} proxies.")


def set_rotation_frequency(freq: int):
    global REQUESTS_PER_PROXY
    try:
        freq = int(freq)
        if freq < 1:
            raise ValueError("Value must be greater than 0")
        REQUESTS_PER_PROXY = freq
        print(f"Proxy rotation frequency set to rotate every {REQUESTS_PER_PROXY} checks.")
    except Exception as e:
        print(f"Failed to set rotation frequency: {e}")


def get_current_proxy() -> Optional[str]:
    global current_proxy_index, current_proxy_request_count
    if not PROXIES:
        return None
    if current_proxy_request_count >= REQUESTS_PER_PROXY:
        current_proxy_index = (current_proxy_index + 1) % len(PROXIES)
        current_proxy_request_count = 0
        print(f"Rotating proxy. New proxy: {PROXIES[current_proxy_index]}")
    current_proxy_request_count += 1
    return PROXIES[current_proxy_index]


def generate_random_fingerprint():
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.6943.54 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.6943.141 Safari/537.36"
    ]
    resolutions = [(1920, 1080), (1600, 900), (1366, 768)]
    webgl_options = [
        "NVIDIA, NVIDIA GeForce GTX 1650 Ti Direct3D9Ex vs_3_0 ps_3_0",
        "Intel, Intel(R) HD Graphics Family Direct3D11 vs_4_1 ps_4_1, D3D11-23.21.13.9135",
        "Intel, Intel(R) Iris(R) Xe Graphics Direct3D11 vs_5_0 ps_5_0, D3D11-27.20.100.9168"
    ]
    return {
        "user_agent": random.choice(user_agents),
        "viewport": {"width": random.choice(resolutions)[0], "height": random.choice(resolutions)[1]},
        "webgl_vendor": "Google Inc.",
        "webgl_renderer": random.choice(webgl_options)
    }


async def add_stealth(page, fingerprint):
    # Inject stealth scripts: hide webdriver property, spoof window dimensions, and spoof WebGL parameters.
    await page.add_init_script("""() => {
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
        Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
    }""")
    await page.add_init_script(f"""() => {{
        Object.defineProperty(window, 'outerWidth', {{get: () => {fingerprint["viewport"]["width"]}}});
        Object.defineProperty(window, 'outerHeight', {{get: () => {fingerprint["viewport"]["height"]}}});
    }}""")
    await page.add_init_script(f"""() => {{
        const getParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(parameter) {{
            if (parameter === 37445) return "{fingerprint['webgl_renderer']}";
            if (parameter === 37446) return "{fingerprint['webgl_vendor']}";
            return getParameter.apply(this, arguments);
        }};
    }}""")


async def check_one_email_in_page(page, identifier, stop_event=None, logger_callback=None):
    """
    Check a single email on one page:
      - If stop_event.is_set(), return None immediately to abort;
      - Fill in the email -> Click the submit button -> Determine if the account is registered
    """
    if stop_event and stop_event.is_set():
        return None

    if logger_callback is None:
        def logger_callback(msg):
            print(msg)

    # Check if CAPTCHA appears on the page
    content_initial = await page.content()
    if ("captchacharacters" in content_initial or
        "/errors/validateCaptcha" in page.url or
        "Type the characters you see" in content_initial):
        logger_callback(f"[{identifier}] CAPTCHA detected. Skipping check.")
        return None

    # Wait for and fill in the email input field
    email_selector = None
    try:
        await page.wait_for_selector("input#ap_email", timeout=8000)
        email_selector = "input#ap_email"
    except PlaywrightTimeoutError:
        try:
            await page.wait_for_selector("input[name='email']", timeout=8000)
            email_selector = "input[name='email']"
        except PlaywrightTimeoutError:
            body_text = await page.text_content("body") or ""
            if "We cannot find an account" in body_text or "We weren't able to identify you" in body_text:
                logger_callback(f"[{identifier}] => Not registered (based on body message)")
                return False
            else:
                logger_callback(f"[{identifier}] Email input field not found. Abnormal page structure.")
                return None

    if stop_event and stop_event.is_set():
        return None

    await page.fill(email_selector, identifier)
    await page.wait_for_timeout(500)

    # Click the submit button
    try:
        await page.wait_for_selector("input[type='submit']", timeout=5000)
        await page.click("input[type='submit']")
    except PlaywrightTimeoutError:
        logger_callback(f"[{identifier}] Submit button not found.")
        return None

    await page.wait_for_load_state("networkidle", timeout=10000)
    await page.wait_for_timeout(1000)

    if stop_event and stop_event.is_set():
        return None

    body_text = await page.text_content("body") or ""
    final_url = page.url

    # Determine registration status based on page content
    if "We cannot find an account" in body_text or "Create your Amazon account" in body_text:
        return False
    if "Enter your password" in body_text:
        return True
    if "Authentication required" in body_text:
        return None
    return None


async def check_registrations_continuous(emails: List[str],
                                         stop_event=None,
                                         logger_callback=None,
                                         progress_callback=None):
    """
    Use an asynchronous approach to continuously check multiple emails within the same browser context.
    """
    results = []
    user_data_dir = tempfile.mkdtemp(prefix="user_data_")
    if logger_callback:
        logger_callback(f"Using temporary data directory: {user_data_dir}")
    else:
        print(f"Using temporary data directory: {user_data_dir}")

    proxy = get_current_proxy()
    fingerprint = generate_random_fingerprint()
    if logger_callback:
        logger_callback(f"Generated random fingerprint: {fingerprint}")
    else:
        print(f"Generated random fingerprint: {fingerprint}")

    # Corrected login_url (using the correct claimed_id parameter)
    login_url = (
        "https://www.amazon.com/ap/signin?"
        "openid.pape.max_auth_age=0&"
        "openid.return_to=https%3A%2F%2Fwww.amazon.com%2Fref%3Dnav_ya_signin&"
        "openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&"
        "openid.assoc_handle=usflex&"
        "openid.mode=checkid_setup&"
        "openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&"
        "openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0"
    )

    try:
        async with async_playwright() as p:
            launch_args = {
                "headless": True,
                "viewport": fingerprint["viewport"],
                "user_agent": fingerprint["user_agent"]
            }
            if proxy:
                launch_args.setdefault("args", []).append(f"--proxy-server={proxy}")

            context = await p.chromium.launch_persistent_context(user_data_dir, **launch_args)
            page = await context.new_page()
            await add_stealth(page, fingerprint)

            for email in emails:
                if stop_event and stop_event.is_set():
                    break

                try:
                    await page.goto(login_url, timeout=30000)
                    await page.wait_for_load_state("networkidle", timeout=15000)
                    await page.wait_for_timeout(1000)

                    if stop_event and stop_event.is_set():
                        break

                    ret = await check_one_email_in_page(page, email,
                                                        stop_event=stop_event,
                                                        logger_callback=logger_callback)
                    if ret is True:
                        logger_callback(f"[{email}] -> Registered")
                        results.append((email, True))
                        # Try clicking the "change" link if available
                        found_change = False
                        all_links = await page.query_selector_all("a")
                        for link in all_links:
                            txt = (await link.inner_text() or "").lower()
                            if "change" in txt:
                                await link.click()
                                await page.wait_for_timeout(1500)
                                found_change = True
                                break
                        if not found_change:
                            logger_callback(f"[{email}] 'change' link not found; re-navigating")
                            await page.goto(login_url, timeout=20000)
                            await page.wait_for_load_state("networkidle", timeout=8000)
                    elif ret is False:
                        logger_callback(f"[{email}] -> Not Registered")
                        results.append((email, False))
                    else:
                        logger_callback(f"[{email}] -> Unknown/Failed")
                        results.append((email, None))

                    if progress_callback:
                        progress_callback(email, ret)

                except Exception as e:
                    import traceback
                    err_msg = f"[{email}] Exception during check: {e}"
                    logger_callback(err_msg)
                    traceback.print_exc()
                    results.append((email, None))
                    if progress_callback:
                        progress_callback(email, None)

            await context.close()

    except Exception as e:
        logger_callback(f"Critical error occurred: {e}")
    return results
