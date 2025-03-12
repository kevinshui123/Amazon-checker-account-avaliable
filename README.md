# Amazon Bulk Login Checker (All in One)

Below is a consolidated Markdown document containing:
1. A **README** section describing the tool (in English).
2. The **playwright_checker.py** code (translated into English).
3. The **ui.py** code (translated into English).

---

## 1. README

### Amazon Login Bulk Checker

Amazon Login Bulk Checker is a GUI tool built in Python that allows you to check a large number of Amazon account emails in bulk to determine if the account is already registered. It leverages Playwright for browser automation with stealth features and asynchronous checks to speed up the process.

#### Features
- **Bulk Account Import**: Load account data from a text file.
- **Email Extraction**: Automatically extract valid email addresses from raw data.
- **Shuffle Order**: Randomize the order of emails before checking.
- **Proxy Support**: Load a list of proxies and configure IP rotation frequency.
- **Asynchronous Checking**: Uses Playwright’s asynchronous APIs and multi-threading for faster results.
- **Real-Time Progress**: Displays progress and counts of registered, unregistered, and unknown results in the GUI.
- **Result Export**: Exports results into separate categories (registered, unregistered, unknown) in a text file.

#### Requirements
- **Python 3.8+**
- **pip** (for installing dependencies)

#### Installation
1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/amazon-checker-account-available.git
   cd amazon-checker-account-available
   
#### Create a virtual environment (optional)
   python -m venv venv
   # Windows:
   venv\Scripts\activate
   # macOS/Linux:
   source venv/bin/activate

#### Install dependencies
   pip install -r requirements.txt
   
   If you don’t have a requirements.txt, you might need the following at a minimum:
   playwright
   pillow
   
#### Install Playwright browsers:
   playwright install
   
#### Usage
   python ui.py


