import time
import requests
import numpy as np
import browser_cookie3
from bs4 import BeautifulSoup
from selenium import webdriver
from dotenv import load_dotenv
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from ChromaDBService import ChromaDBService


class AuthDetector(ChromaDBService):
    
    def __init__(self):
        load_dotenv()
        super().__init__()
        self.intents = {
            "schedule": "asking about class schedule, timetable, or next class, instructor, room, days or subject and code",
            "grades": "asking about grades, marks, GPA, or academic performance",
            "soa": "asking about statement of account, balance, assessment fees",
            "clearance": "asking about academic clearance",
            "general": "asking about general questions such as enrollments or enrollment requirements or step by step process of enrollment, programs, courses, strands, track, associate or degree courses, school fees, tuition, miscellaneous, downpayment or other fees, student affairs service office (saso), department laws, regulations, violations, start and end of classes, first, second, third and fourth grading elementary, preschool, college, freshmen, incoming first year, new students, old students senior high and junior high school, violations, who is the founder, violations,  Requirements for the Renewal of Recognition, preamble, scholarship, scholarship grant, school fees"
        }
        # i-uncomment ito kapag gagamitin na yung web scraping para ma detect yung intent.
        # self.auth_required_intents = ["schedule", "grades", "soa", "clearance"]
        
        self.session = None
        self.base_url = "https://srv1.thelewiscollege.edu.ph/mytlc/index.php"
        self.urls = {
            'schedule': f"{self.base_url}/student/schedule",
            'grades': f"{self.base_url}/student/grades",
            'soa': f"{self.base_url}/student/soa",
            'clearance': f"{self.base_url}/student/clearance"
        }

    def _compute_intent_embeddings(self):
        embeddings = {}
        for key, description in self.intents.items():
            response = self.openai_client.embeddings.create(
                model=self.embedding_model,
                input=description
            )
            # extracting embedding
            emb_data = response.data[0].embedding
            embeddings[key] = np.array(emb_data, dtype=float) 
        
        return embeddings

    def detect_intent(self, prompt: str):
        response = self.openai_client.embeddings.create(
            model=self.embedding_model,
            input=prompt
        )
        prompt_emb = np.array(response.data[0].embedding, dtype=float)  
        
        intent_embeddings = self._compute_intent_embeddings()
        
        similarities = {}
        for key, emb in intent_embeddings.items():
            emb_array = np.array(emb, dtype=float)
            similarity = np.dot(prompt_emb, emb_array) / (np.linalg.norm(prompt_emb) * np.linalg.norm(emb_array))
            similarities[key] = similarity
        
        return max(similarities, key=similarities.get), similarities
    
    def requires_authentication(self, intent: str) -> bool:
        # sa ngayon return false lang muna
        # pero kapag itest na yung web scraping i activate lang yung intent
        # then i deactivate yung false.
        # return intent in self.auth_required_intents
        return False
      
    def get_cookies(self):
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
        print(f"\nAttempting Selenium login for: {username}")
        
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        driver = webdriver.Chrome(options=chrome_options)
        
        try:
            driver.get(f"{self.base_url}/login")
            
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
        print(f"\nExtracting: {page_name.upper()}")
        
        response = self.session.get(url)
        
        if response.status_code == 200 and "login" not in response.url:
            soup = BeautifulSoup(response.text, 'html.parser')
            tables = soup.find_all('table')

            extracted_data = f"\n=== {page_name.upper()} DATA ===\n"
            
            if tables:
                for i, table in enumerate(tables):
                    extracted_data += f"\n--- Table {i+1} ---\n"
                    for row in table.find_all('tr'):
                        cells = row.find_all(['td', 'th'])
                        row_data = [cell.get_text(strip=True) for cell in cells]
                        if any(row_data):
                            row_text = " | ".join(row_data)
                            print(row_text)  
                            extracted_data += row_text + "\n" 
            else:
                no_tables_msg = "No tables found"
                print(no_tables_msg)
                extracted_data += no_tables_msg + "\n"
            
            return extracted_data  
        
        print(f"Could not access {page_name}")
        return None  
    
    def scrape(self):
        print("TLC Smart Auto-Scraper")
        
        print("\n1. Trying automatic cookie extraction...")
        self.session = self.get_cookies()
        
        if self.session:
            print("Automatic method worked!")
            return self._extract_all_data()
        
        print("\nAutomatic login failed. Please use /student/login endpoint.")
        return False
    
    def _extract_all_data(self):
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