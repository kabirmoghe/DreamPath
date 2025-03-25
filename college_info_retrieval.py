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

CHROME_OPTIONS = Options()
CHROME_OPTIONS.add_argument("--headless")

def get_dartmouth_degrees():
    """
    Scrapes Dartmouth College's degrees page to retrieve all bachelor's degree majors
    and their associated departments using Selenium.
    
    Returns:
        pandas.DataFrame: DataFrame containing majors and their departments
    """
    
    # Initialize the WebDriver
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=CHROME_OPTIONS
    )
    
    base_url = 'https://home.dartmouth.edu/degrees'
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
                    major_name = major_text.split("(Bachelor of")[0].strip()
                    
                    # Extract degree type
                    degree_type = "Bachelor of " + major_text.split("Bachelor of")[1].strip(")")
                    
                    majors_data.append({
                        'Major': major_name,
                        'Department': dept['text'],
                        'Degree Type': degree_type,
                        'URL': major_elem.get_attribute('href')
                    })
                    
                    print(f"  Found major: {major_name}")
        
        print(f"Total majors found: {len(majors_data)}")
        
    except Exception as e:
        print(f"An error occurred: {e}")
    
    # Convert to DataFrame
    df = pd.DataFrame(majors_data)
    return df

def get_undergraduate_links_by_major(major_df, major_name):
    """
    Navigates to a specific major's URL and finds all links to undergraduate courses.
    
    Args:
        major_df (pandas.DataFrame): DataFrame containing major information
        major_name (str): Name of the major to look up
        
    Returns:
        dict: Information about the major's courses
    """
    # Get the URL for the specified major
    try:
        major_url = major_df[major_df['Major'] == major_name]['URL'].values[0]
    except (IndexError, KeyError):
        print(f"Major '{major_name}' not found in the DataFrame")
        return None
    
    # Setup Chrome options
    chrome_options = Options()
    chrome_options.add_experimental_option("detach", True)
    # chrome_options.add_argument("--headless")  # Run in headless mode
    
    # Initialize the WebDriver
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=CHROME_OPTIONS
    )

    undergraduate_courses_links = []
    
    try:
        # Navigate to the major's URL
        print(f"Navigating to: {major_url}")
        driver.get(major_url)
        time.sleep(3)  # Wait for page to load
        
        # Look for the right panel
        try:
            right_panel = driver.find_element(By.ID, "rightpanel")
            links = right_panel.find_elements(By.TAG_NAME, "a")
            
            # Look for links containing 'undergraduate' in URL and 'here' in text
            for link in links:
                link_text = link.text.lower()
                link_href = link.get_attribute('href').lower()
                
                if ('undergraduate' in link_href) and ('here' in link_text):
                    undergraduate_link = {
                        'text': link.text,
                        'url': link.get_attribute('href')
                    }

                    undergraduate_courses_links.append(undergraduate_link)
                    print(f"* Found undergraduate link: {link.text} - {link.get_attribute('href')}")
            
            if undergraduate_courses_links:
                print(f"Found {len(undergraduate_courses_links)} undergraduate links for {major_name}")
            else:
                print(f"Could not find any undergraduate links for {major_name}")
        
        except NoSuchElementException:
            print(f"Could not find right panel on the page for {major_name}")

    except Exception as e:
        print(f"An error occurred while processing {major_name}: {e}")
    
    finally:
        # Close the browser
        driver.quit()
    
    return undergraduate_courses_links

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
                            'dept': dept_abbr,
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
            
            # Extract course information based on the provided HTML structure
            
            # Course code
            course_header = soup.select_one('#rightpanel #main h1')
            course_code = ""
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

def produce_courses_for_major(major):
    majors_df = pd.read_csv('data/dartmouth_majors.csv')
    undergraduate_links = get_undergraduate_links_by_major(majors_df, major)

    if undergraduate_links:
        courses = get_courses_by_link(undergraduate_links)

        if courses:
            # Get course descriptions
            courses_with_descriptions = get_course_descriptions(courses)

            return courses_with_descriptions
        else:
            print("No courses found")
            return None
    else:
        print(f"No undergraduate course links found for {major}")
        return None
