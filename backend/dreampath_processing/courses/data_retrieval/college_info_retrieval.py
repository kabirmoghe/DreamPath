import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import Select
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import NoSuchElementException
import requests
from bs4 import BeautifulSoup
import os
from rapidfuzz import process, fuzz
import unicodedata
from dreampath_processing.courses.data_retrieval.prerequisite_parsing import get_course_prereqs
import uuid

CHROME_OPTIONS = Options()
CHROME_OPTIONS.add_argument("--headless")

DEGREES_URL = 'https://home.dartmouth.edu/degrees'
DEPARTMENTS_URL = 'https://dartmouth.smartcatalogiq.com/en/current/orc/departments-programs-undergraduate'

# Use absolute path based on this file's location (works regardless of CWD)
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")

def normalize_text(text):
    """
    Normalize text by replacing Unicode quotation marks with regular apostrophes
    and handling other common Unicode characters.
    
    Args:
        text (str): Text to normalize
        
    Returns:
        str: Normalized text
    """
    if not text:
        return text
    
    # Replace common Unicode quotation marks with regular apostrophes
    text = text.replace('\u2019', "'")  # Right single quotation mark
    text = text.replace('\u2018', "'")  # Left single quotation mark
    text = text.replace('\u201c', '"')  # Left double quotation mark
    text = text.replace('\u201d', '"')  # Right double quotation mark
    text = text.replace('\u2013', '-')  # En dash
    text = text.replace('\u2014', '—')  # Em dash
    
    # Normalize other Unicode characters to their closest ASCII equivalents
    text = unicodedata.normalize('NFKD', text)
    
    return text.strip()

def get_department_data():
    """
    Scrapes Dartmouth's catalog navigation to get department names and their associated course links.
    Navigates through the nested menu structure to collect all department-to-courses mappings.
    
    Returns:
        dict: Dictionary mapping department names to lists of course link dictionaries
    """
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=CHROME_OPTIONS
    )
    
    catalog_url = "https://dartmouth.smartcatalogiq.com/current/orc"
    department_data = {}
    
    try:
        # Navigate to the catalog page
        driver.get(catalog_url)
        time.sleep(3)  # Wait for page to load
        
        # Find the navLocal ul element
        nav_local = driver.find_element(By.ID, "navLocal")
        
        # Find all li elements with class "hasChildren"
        has_children_items = nav_local.find_elements(By.CSS_SELECTOR, "li.hasChildren")
        
        if len(has_children_items) < 5:
            print(f"Expected at least 5 hasChildren items, found {len(has_children_items)}")
            return department_data
        
        # Get the 5th hasChildren item (index 4)
        fifth_item = has_children_items[4]
        
        # Find and click the button in the 5th item to expand it
        try:
            expand_button = fifth_item.find_element(By.CSS_SELECTOR, "button")
            expand_button.click()
            time.sleep(2)  # Wait for expansion
            print("Clicked main expand button")
        except Exception as e:
            print(f"Error clicking main expand button: {e}")
            return department_data
        
        # Now find the expanded ul within the 5th item
        try:
            expanded_ul = fifth_item.find_element(By.TAG_NAME, "ul")
            department_items = expanded_ul.find_elements(By.CSS_SELECTOR, "li.hasChildren")
            print(f"Found {len(department_items)} department items")
        except Exception as e:
            print(f"Error finding expanded department list: {e}")
            return department_data
        
        # UUID for each department
        dept_ids = {}

        # Process each department
        for i, dept_item in enumerate(department_items):
            try:
                # Get the department name from the link text
                dept_link = dept_item.find_element(By.TAG_NAME, "a")
                dept_name = normalize_text(dept_link.text.split('-')[0].strip())

                # Special case for Classics
                if dept_name == "Classics Classical Studies Greek Latin":
                    dept_name = "Classics"

                print(f"Processing department {i+1}/{len(department_items)}: {dept_name}")

                # Assign a UUID to the department using UUID5
                dept_id = str(uuid.uuid5(uuid.NAMESPACE_URL, dept_name))
                dept_ids[dept_name] = dept_id

                # Find and click the expand button for this department
                try:
                    dept_button = dept_item.find_element(By.CSS_SELECTOR, "button")
                    dept_button.click()
                    time.sleep(1.5)  # Wait for department expansion
                except Exception as e:
                    print(f"Error clicking button for {dept_name}: {e}")
                    continue
                
                # Find the expanded ul within this department
                try:
                    dept_expanded_ul = dept_item.find_element(By.TAG_NAME, "ul")
                    course_items = dept_expanded_ul.find_elements(By.CSS_SELECTOR, "li.hasChildren")
                    
                    course_links = []
                    for i, course_item in enumerate(course_items):
                        try:
                            course_link = course_item.find_element(By.TAG_NAME, "a")
                            course_text = normalize_text(course_link.text.strip())
                            course_url = course_link.get_attribute('href')
                            
                            if course_text and course_url:
                                course_links.append({
                                    'text': course_text,
                                    'url': course_url
                                    })

                        except Exception as e:
                            # Some li items might not have links, skip them
                            continue
                    
                    department_data[dept_name] = course_links
                    print(f"  Found {len(course_links)} course links for {dept_name}")
                    
                except Exception as e:
                    print(f"Error finding course links for {dept_name}: {e}")
                    department_data[dept_name] = []

                # Remove empty departments
                if not department_data[dept_name]:
                    del department_data[dept_name]
                
            except Exception as e:
                print(f"Error processing department item {i}: {e}")
                continue
        
        print(f"Total departments processed: {len(department_data)}")
        
    except Exception as e:
        print(f"An error occurred while scraping department data: {e}")
    
    finally:
        # Close the browser
        driver.quit()
    
    return department_data, dept_ids

def get_department_id(department, dept_ids, score_cutoff=50):
    match, score, _ = process.extractOne(
        department.strip("'"), dept_ids.keys(), scorer=fuzz.token_sort_ratio
    )

    print(f"For department {department}, found match {match} with score {score}")

    if score >= score_cutoff:
        return dept_ids[match]
    else:
        return None

def get_dartmouth_majors(dept_ids):
    """
    Scrapes Dartmouth College's degrees page to retrieve all bachelor's degree majors and their associated departments using Selenium.
    
    Returns:
        pandas.DataFrame: DataFrame containing majors and their departments
    """
    
    # Initialize the WebDriver
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=CHROME_OPTIONS
    )
    
    base_url = DEGREES_URL
    majors_data = []
    
    try:
        # Navigate to the degrees page
        driver.get(base_url)
        time.sleep(2)

        # Filter degree type
        type_select = Select(driver.find_element(By.ID, 'edit-type'))
        
        # Find the value for Bachelor's degrees
        bachelor_value = None
        for option in type_select.options:
            if "Bachelor" in option.text:
                bachelor_value = option.get_attribute('value')
                break
        
        if bachelor_value:
            type_select.select_by_value(bachelor_value)
            print(f"Selected Bachelor's degree type with value: {bachelor_value}")
        else:
            print("Could not find Bachelor option in the dropdown")
            return None
            
        # Wait for the page to update
        time.sleep(2)
        
        # Get all departments from the dropdown
        department_select = Select(driver.find_element(By.ID, "edit-department"))
        departments = []
        
        for option in department_select.options:
            value = option.get_attribute('value')
            text = option.text
            if value and value != 'All':  # Skip the "All" option
                departments.append({'value': value, 'text': text})
        
        print(f"Found {len(departments)} departments")
        
        # Process each department
        for dept in departments:
            print(f"Processing department: {dept['text']}")
            
            # Select the department
            department_select = Select(driver.find_element(By.ID, "edit-department"))
            department_select.select_by_value(dept['value'])
            
            # Wait for results to load
            time.sleep(2)
            
            # Find all major links
            major_elements = driver.find_elements(By.CSS_SELECTOR, ".field-content a")
            
            for major_elem in major_elements:
                major_text = major_elem.text
                
                # Check if it's a Bachelor's degree
                if "(Bachelor of" in major_text:
                    # Extract major name
                    major_name = normalize_text(major_text.split("(Bachelor of")[0].strip())
                    
                    # Extract degree type
                    degree_type = "Bachelor of " + major_text.split("Bachelor of")[1].strip(")")
                    
                    majors_data.append({
                        'major': major_name,
                        'department': normalize_text(dept['text'].replace("Department", "").strip()),
                        'degree_type': degree_type,
                        'url': major_elem.get_attribute('href')
                    })
                    
                    print(f"  Found major: {major_name}")
        
        print(f"Total majors found: {len(majors_data)}")
        
    except Exception as e:
        print(f"An error occurred: {e}")
    
    # Convert to DataFrame
    df = pd.DataFrame(majors_data)
    df['department_id'] = df['department'].apply(lambda x: get_department_id(x, dept_ids))

    return df

def get_courses_by_link(courses_links):
    """
    Navigates to each undergraduate course link and extracts course information.
    
    Args:
        courses_links (list): List of dictionaries containing undergraduate course links
        
    Returns:
        list: List of dictionaries containing course information
    """
    # Setup Chrome options
    chrome_options = Options()
    chrome_options.add_experimental_option("detach", True)
    # chrome_options.add_argument("--headless")  # Run in headless mode
    
    # Initialize the WebDriver
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=CHROME_OPTIONS
    )
    
    courses_list = []
    
    try:
        for link in courses_links:
            print(f"Navigating to: {link['url']}")
            driver.get(link['url'])
            time.sleep(3)  # Wait for page to load
            
            try:
                # Get the department heading and extract abbreviation
                dept_heading = driver.find_element(By.CSS_SELECTOR, "#rightpanel h1").text
                dept_abbr = dept_heading.split(' -')[0].strip()
                print(f"Department abbreviation: {dept_abbr}")
                
                # Find all course links (links that don't contain 'here')
                course_links = driver.find_elements(By.CSS_SELECTOR, "#rightpanel a")
                
                for course_link in course_links:
                    link_text = course_link.text.lower()
                    link_href = course_link.get_attribute('href')
                    
                    # Skip links containing 'here'
                    if 'here' in link_text:
                        continue
                    
                    # Extract course information
                    course_title = course_link.text.strip()
                    
                    if course_title:  # Only process non-empty titles
                        course_info = {
                            'course_title': course_title,
                            'course_url': link_href
                        }
                        courses_list.append(course_info)
                        print(f"Found course: {course_title}")
                
                print(f"Found {len(courses_list)} courses for this link")
                
            except NoSuchElementException as e:
                print(f"Error finding elements: {e}")
            except Exception as e:
                print(f"Error processing link {link['url']}: {e}")
    
    except Exception as e:
        print(f"An error occurred: {e}")
    
    finally:
        # Close the browser
        driver.quit()
    
    return courses_list

def get_course_descriptions(courses_list):
    """
    Navigates to each course URL and extracts the course description and other relevant information.
    
    Args:
        courses_list (list): List of dictionaries containing course information
        
    Returns:
        list: Enhanced list of dictionaries with course descriptions
    """
    courses_with_descriptions = []
    
    for i, course in enumerate(courses_list):
        try:
            print(f"Processing course {i+1}/{len(courses_list)}: {course['course_title']}")
            
            # Get the course page
            response = requests.get(course['course_url'])
            if response.status_code != 200:
                print(f"Failed to retrieve course page: {response.status_code}")
                continue
                
            # Parse the HTML
            soup = BeautifulSoup(response.text, 'html.parser')
                        
            # Course code
            course_header = soup.select_one('#rightpanel #main h1')
            course_code = ""
            code_span = None
            if course_header:
                code_span = course_header.select_one('span')
                if code_span:
                    course_code = (''.join(code_span.text.strip().split()[0:2]))
            
            # Description
            description = ""
            desc_div = soup.select_one('#rightpanel #main .desc')
            if desc_div:
                description = desc_div.get_text(strip=True)
            
            # Prerequisites
            prerequisites = ""
            prereq_div = soup.select_one('#rightpanel .sc_prereqs')
            if prereq_div:
                prerequisites = prereq_div.get_text(strip=True).replace('Prerequisite', '').strip()
            
            # Degree requirements
            degree_req = ""
            req_div = soup.select_one('#rightpanel .sc-extrafield')
            if req_div:
                degree_req = req_div.get_text(strip=True).replace('Degree Requirement Attributes', '').strip()
            
            # Create enhanced course object
            enhanced_course = {
                **course,  # Include all original fields
                'course_code': course_code,
                'description': description,
                'prerequisites': prerequisites,
                'degree_req': degree_req,
                'html_content': response.text  # Store the full HTML for later parsing if needed
            }

            # Improve course title
            if code_span:
                enhanced_course['course_title'] = enhanced_course['course_title'].replace(code_span.text.strip(), "")
            
            courses_with_descriptions.append(enhanced_course)
            print(f"  Extracted description: {description[:100]}..." if description else "  No description found")
            
            # Be nice to the server
            time.sleep(1)
            
        except Exception as e:
            print(f"Error processing course {course.get('course_title', 'Unknown')}: {e}")
            # Still add the course with what we have
            courses_with_descriptions.append({
                **course,
                'Error': str(e)
            })
    
    return courses_with_descriptions

def produce_courses_for_department(department_data, department, department_id):
    # load undergraduate links either from master or retrieval
    major_undergraduate_links = department_data[department]

    # if undergraduate links found, get courses from links
    if major_undergraduate_links:
        courses = get_courses_by_link(major_undergraduate_links)

        # if courses found, get descriptions
        if courses:
            courses_with_descriptions = get_course_descriptions(courses)
        else:
            print(f"No courses found for {department} from undergraduate links.")
            return None

        courses_df = pd.DataFrame(courses_with_descriptions)

        # Remove rows with null course_code
        courses_df = courses_df[courses_df['course_code'].notna()]

        # Add department id
        courses_df['department'] = department
        courses_df['department_id'] = department_id

        return courses_df
    else:
        print(f"No undergraduate links found for {department}")
        return None

def add_prereqs_to_department_data(department_courses_df):
    department_courses_df['best_prereq_path'] = department_courses_df.apply(get_course_prereqs, axis=1, overwrite=False)
    
    return department_courses_df

def load_dataframes(paths):
    rows = []
    for p in paths:
        print(f"Loading '{p}'...")
        if os.path.isdir(p):
            for name in sorted(os.listdir(p)):
                if name.lower().endswith(".csv"):
                    rows.append(pd.read_csv(os.path.join(p, name)))
        else:
            rows.append(pd.read_csv(p))
    if not rows:
        raise SystemExit("No CSVs found.")
    return pd.concat(rows, ignore_index=True)