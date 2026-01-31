import requests
from bs4 import BeautifulSoup
import browser_cookie3
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time
from VirtualFrontDesk import VirtualFrontDesk


class Scraping(VirtualFrontDesk):
    """Smart web scraper for TLC student portal"""
    
    def __init__(self):
        super().__init__()  # Initialize PromptHandler
        self.session = None
        self.base_url = "https://srv1.thelewiscollege.edu.ph/mytlc/index.php"
        self.urls = {
            'schedule': f"{self.base_url}/student/schedule",
            'grades': f"{self.base_url}/student/grades",
            'soa': f"{self.base_url}/student/soa",
            'clearance': f"{self.base_url}/student/clearance"
        }
        
    def get_cookies(self):
        """Enhanced cookie extraction"""
        print("Enhanced cookie extraction...")
        
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        browsers = [
            ('Chrome', browser_cookie3.chrome),
            ('Firefox', browser_cookie3.firefox),
            ('Edge', browser_cookie3.edge),
        ]
        
        for name, browser_func in browsers:
            try:
                print(f"Trying {name}...")
                cookies = browser_func()
                
                if cookies:
                    for cookie in list(cookies):
                        session.cookies.set(cookie.name, cookie.value)
                    
                    test_response = session.get(self.urls['grades'])
                    
                    if "login" not in test_response.url:
                        print(f"SUCCESS with {name}!")
                        return session
                        
            except Exception as e:
                print(f"{name}: {str(e)[:50]}...")
                continue
        
        return None
    
    def login_with_selenium(self, username, password):
        """Login using Selenium automation"""
        print(f"\nAttempting Selenium login for: {username}")
        
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        driver = webdriver.Chrome(options=chrome_options)
        
        try:
            driver.get(f"{self.base_url}/login")
            
            # Find username field
            username_field = None
            for selector in ["input[type='text']", "input[name*='user']", "input[name='username']"]:
                try:
                    username_field = driver.find_element(By.CSS_SELECTOR, selector)
                    break
                except:
                    continue
            
            if not username_field:
                return None
            
            password_field = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
            username_field.send_keys(username)
            password_field.send_keys(password)
            
            # Find and click login button
            login_btn = None
            for selector in ["input[type='submit']", "button[type='submit']", ".btn"]:
                try:
                    login_btn = driver.find_element(By.CSS_SELECTOR, selector)
                    if login_btn.is_displayed() and login_btn.is_enabled():
                        break
                except:
                    continue
            
            if not login_btn:
                return None
            
            login_btn.click()
            time.sleep(5)
            
            # Check login success
            login_success = "login" not in driver.current_url.lower()
            
            if login_success:
                print("Login successful!")
                
                session = requests.Session()
                session.headers.update({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                
                for cookie in driver.get_cookies():
                    session.cookies.set(cookie['name'], cookie['value'])
                
                return session
            
            return None
                
        except Exception as e:
            print(f"Selenium login error: {str(e)}")
            return None
        finally:
            driver.quit()
    
    def extract_data(self, url, page_name):
        """Extract data from a specific page"""
        print(f"\nExtracting: {page_name.upper()}")
        
        response = self.session.get(url)
        
        if response.status_code == 200 and "login" not in response.url:
            soup = BeautifulSoup(response.text, 'html.parser')
            tables = soup.find_all('table')
            
            if tables:
                for i, table in enumerate(tables):
                    print(f"\n--- Table {i+1} ---")
                    for row in table.find_all('tr'):
                        cells = row.find_all(['td', 'th'])
                        row_data = [cell.get_text(strip=True) for cell in cells]
                        if any(row_data):
                            print(" | ".join(row_data))
            else:
                print("No tables found")
            
            return True
        
        print(f"Could not access {page_name}")
        return False
    
    def scrape(self):
        """Main scraping method - uses credentials from student_login"""
        print("TLC Smart Auto-Scraper")
        
        # Method 1: Cookie extraction
        print("\n1. Trying automatic cookie extraction...")
        self.session = self.get_cookies()
        
        if self.session:
            print("Automatic method worked!")
            return self._extract_all_data()
        
        print("\nAutomatic login failed. Please use /student/login endpoint.")
        return False
    
    def _extract_all_data(self):
        """Extract data from all pages"""
        if not self.session:
            print("No active session")
            return False
        
        print("\nEXTRACTING ALL STUDENT DATA")
        
        results = {}
        for page_name, url in self.urls.items():
            results[page_name] = self.extract_data(url, page_name)
            time.sleep(1)
        
        print("\nEXTRACTION SUMMARY")
        for page_name, success in results.items():
            status = "✓ Success" if success else "✗ Failed"
            print(f"{page_name.capitalize():15} : {status}")
        
        return any(results.values())