import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
import io

# Set page configuration
st.set_page_config(
    page_title="Sunbiz Business Owner Scraper",
    page_icon="📊",
    layout="centered"
)

# Custom CSS for clean, minimal styling
st.markdown("""
<style>
    .main {
        background-color: #FFFFFF;
    }
    .stButton>button {
        background-color: #0083B8;
        color: white;
        border-radius: 4px;
        padding: 0.5rem 1rem;
        font-weight: 500;
    }
    .stProgress > div > div {
        background-color: #0083B8;
    }
    h1, h2, h3 {
        color: #333333;
    }
    .stAlert {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
    }
</style>
""", unsafe_allow_html=True)

# App header
st.title("Sunbiz Business Owner Scraper")
st.markdown("Extract business owner information from Florida's Sunbiz registry and export to CSV.")

# Input fields
st.subheader("Search Parameters")

search_type = st.selectbox(
    "Search Type",
    ["Business Name", "Document Number"]
)

if search_type == "Business Name":
    search_term = st.text_input("Enter Business Name", placeholder="e.g., Acme Corporation")
else:
    search_term = st.text_input("Enter Document Number", placeholder="e.g., L21000123456")

max_results = st.slider("Maximum Results to Scrape", min_value=1, max_value=50, value=10)

# Function to scrape Sunbiz search results
def search_sunbiz(search_type, search_term, max_results):
    results = []
    
    # Create base search URL based on search type
    if search_type == "Business Name":
        base_url = "http://search.sunbiz.org/Inquiry/CorporationSearch/SearchResults/EntityName/{}".format(search_term.replace(" ", "%20"))
    else:
        base_url = "http://search.sunbiz.org/Inquiry/CorporationSearch/SearchResults/DocumentNumber/{}".format(search_term)
    
    try:
        # Send request with headers to mimic browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # Start with page 1
        current_page = 1
        count = 0
        
        while count < max_results:
            # Construct URL for current page
            page_url = f"{base_url}/Page{current_page}"
            
            # Update status
            status_text.text(f"Searching page {current_page}...")
            
            response = requests.get(page_url, headers=headers)
            
            if response.status_code != 200:
                if current_page == 1:  # If first page fails, return error
                    return {"success": False, "message": f"Error: Received status code {response.status_code}"}
                else:  # If subsequent page fails, we've likely reached the end
                    break
            
            # Parse the search results page
            soup = BeautifulSoup(response.text, 'html.parser')
            search_results = soup.select('tr.searchResultsTable')
            
            if not search_results:
                if current_page == 1:  # If first page has no results, return error
                    return {"success": False, "message": "No results found. Try a different search term."}
                else:  # If subsequent page has no results, we've reached the end
                    break
            
            # Process each search result up to max_results
            for result in search_results:
                if count >= max_results:
                    break
                    
                # Extract basic info from search results
                name_element = result.select_one('a')
                if not name_element:
                    continue
                    
                business_name = name_element.text.strip()
                detail_url = "http://search.sunbiz.org" + name_element['href']
                
                # Status info
                status_element = result.select_one('td:nth-of-type(2)')
                status = status_element.text.strip() if status_element else "Unknown"
                
                # Get detailed information
                status_text.text(f"Processing: {count+1}/{max_results} - {business_name}")
                detail_info = get_business_details(detail_url)
                
                if detail_info["success"]:
                    results.append({
                        "Business Name": business_name,
                        "Status": status,
                        "Document Number": detail_info.get("Document Number", ""),
                        "FEI/EIN Number": detail_info.get("FEI/EIN Number", ""),
                        "Owner Name": detail_info.get("Owner Name", ""),
                        "Owner Title": detail_info.get("Owner Title", ""),
                        "Owner Email": detail_info.get("Owner Email", ""),
                        "Address": detail_info.get("Address", ""),
                        "Filing Date": detail_info.get("Filing Date", "")
                    })
                    count += 1
                    
                    # Update progress
                    progress_bar.progress(count / max_results)
                    time.sleep(0.5)  # Small delay to avoid aggressive scraping
                
                if count >= max_results:
                    break
            
            # Check if there's a next page
            next_page_link = soup.select_one('a.navigationLink:contains("Next")')
            if not next_page_link:
                # No more pages
                break
                
            # Move to next page
            current_page += 1
            
        return {"success": True, "data": results}
    
    except Exception as e:
        return {"success": False, "message": f"Error: {str(e)}"}

# Function to get business details from detail page
def get_business_details(detail_url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        }
        
        response = requests.get(detail_url, headers=headers)
        
        if response.status_code != 200:
            return {"success": False, "message": f"Error accessing detail page: {response.status_code}"}
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract document number
        doc_number = ""
        doc_label = soup.find(string=re.compile("Document Number"))
        if doc_label and doc_label.find_parent():
            doc_number_element = doc_label.find_parent().find_next_sibling()
            if doc_number_element:
                doc_number = doc_number_element.text.strip()
        
        # Extract FEI/EIN Number
        fei_number = ""
        fei_label = soup.find(string=re.compile("FEI/EIN Number"))
        if fei_label and fei_label.find_parent():
            fei_number_element = fei_label.find_parent().find_next_sibling()
            if fei_number_element:
                fei_number = fei_number_element.text.strip()
        
        # Extract filing date
        filing_date = ""
        date_label = soup.find(string=re.compile("Date Filed"))
        if date_label and date_label.find_parent():
            date_element = date_label.find_parent().find_next_sibling()
            if date_element:
                filing_date = date_element.text.strip()
        
        # Extract address
        address = ""
        address_header = soup.find(string=re.compile("Principal Address"))
        if address_header and address_header.find_parent():
            address_section = address_header.find_parent().find_next_sibling()
            if address_section:
                address = address_section.text.strip().replace('\n', ', ')
        
        # Extract officer/owner information
        owner_name = ""
        owner_title = ""
        owner_email = ""
        
        # Look for officer/registered agent sections
        officer_sections = soup.find_all(string=re.compile("Officer/Director Detail"))
        if officer_sections:
            for section in officer_sections:
                section_parent = section.find_parent()
                if section_parent:
                    # Find the table containing officer details
                    officer_table = section_parent.find_next('table')
                    if officer_table:
                        # Get all officers
                        officer_rows = officer_table.find_all('tr')
                        if officer_rows:
                            # Get the first officer by default
                            name_cell = officer_rows[0].find('td')
                            if name_cell:
                                owner_name = name_cell.text.strip()
                            
                            title_cells = officer_rows[0].find_all('td')
                            if len(title_cells) > 1:
                                owner_title = title_cells[1].text.strip()
                            
                            # Look for President or CEO first if available
                            for row in officer_rows:
                                cells = row.find_all('td')
                                if len(cells) > 1:
                                    title = cells[1].text.strip().lower()
                                    if "president" in title or "ceo" in title or "chief executive" in title:
                                        owner_name = cells[0].text.strip()
                                        owner_title = cells[1].text.strip()
                                        break
                            
                            # Look for email in all text
                            page_text = soup.get_text()
                            email_matches = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', page_text)
                            if email_matches:
                                # Filter out common false positives
                                filtered_emails = [email for email in email_matches 
                                                if not email.endswith('@sunbiz.org') 
                                                and not email.endswith('@dos.myflorida.com')]
                                if filtered_emails:
                                    owner_email = filtered_emails[0]
                            
                            break  # We've found what we need
        
        # If no officers found, try registered agent
        if not owner_name:
            agent_section = soup.find(string=re.compile("Registered Agent"))
            if agent_section and agent_section.find_parent():
                agent_info = agent_section.find_parent().find_next_sibling()
                if agent_info:
                    owner_name = agent_info.text.strip().split('\n')[0]
                    owner_title = "Registered Agent"
        
        # If no email found, try to find in mailing address
        if not owner_email:
            mailing_header = soup.find(string=re.compile("Mailing Address"))
            if mailing_header and mailing_header.find_parent():
                mailing_section = mailing_header.find_parent().find_next_sibling()
                if mailing_section:
                    mailing_text = mailing_section.text
                    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', mailing_text)
                    if email_match:
                        owner_email = email_match.group(0)
        
        return {
            "success": True,
            "Document Number": doc_number,
            "FEI/EIN Number": fei_number,
            "Owner Name": owner_name,
            "Owner Title": owner_title,
            "Owner Email": owner_email,
            "Address": address,
            "Filing Date": filing_date
        }
        
    except Exception as e:
        return {"success": False, "message": f"Error extracting details: {str(e)}"}

# Function to convert results to CSV
def convert_to_csv(data):
    df = pd.DataFrame(data)
    csv = df.to_csv(index=False)
    return csv

# Create a button to start scraping
start_button = st.button("Start Scraping")

# Initialize session state for results
if 'results' not in st.session_state:
    st.session_state.results = None

if start_button:
    if not search_term:
        st.error("Please enter a search term.")
    else:
        # Create a progress bar and status text
        progress_bar = st.progress(0)
        status_text = st.empty()
        status_text.text("Starting search...")
        
        # Run the scraper
        results = search_sunbiz(search_type, search_term, max_results)
        
        # Reset progress indicators
        progress_bar.empty()
        status_text.empty()
        
        if results["success"]:
            st.session_state.results = results["data"]
            st.success(f"Found {len(results['data'])} businesses.")
        else:
            st.error(results["message"])

# Display results if available
if st.session_state.results:
    st.subheader("Search Results")
    
    # Display as a table
    st.dataframe(st.session_state.results)
    
    # Create CSV download button
    csv_data = convert_to_csv(st.session_state.results)
    
    # Create a download button for the CSV
    st.download_button(
        label="Download CSV",
        data=csv_data,
        file_name=f"sunbiz_results_{search_term.replace(' ', '_')}.csv",
        mime="text/csv"
    )

# Footer with disclaimer
st.markdown("---")
st.caption("""
**Disclaimer:** This tool scrapes publicly available information from the Florida Department of State Division of Corporations website (Sunbiz.org). 
Please ensure your use complies with Sunbiz terms of service and applicable laws. This tool is for informational purposes only.
""")
