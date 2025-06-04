import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
import io
import csv

# Set page configuration
st.set_page_config(
    page_title="Sunbiz Business Owner Scraper",
    page_icon="📊",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Custom CSS for clean, minimal styling
st.markdown("""
<style>
    .main {
        background-color: #FFFFFF;
        padding: 2rem;
    }
    .stButton>button {
        background-color: #0083B8;
        color: white;
        border-radius: 4px;
        padding: 0.75rem 1.5rem;
        font-weight: 500;
        width: 100%;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background-color: #006491;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
    }
    .stProgress > div > div {
        background-color: #0083B8;
    }
    h1 {
        color: #0083B8;
        font-weight: 700;
        margin-bottom: 1.5rem;
    }
    h2, h3 {
        color: #333333;
        margin-top: 1.5rem;
    }
</style>
""", unsafe_allow_html=True)

# App header
st.title("Sunbiz Business Owner Scraper")
st.markdown("Extract business owner information from Florida's Sunbiz registry and export to CSV.")

# Create a card-like container for the search form
st.markdown("""
<div style="background-color: #f8f9fa; padding: 1.5rem; border-radius: 8px; border: 1px solid #e9ecef; margin-bottom: 2rem;">
    <h3 style="margin-top: 0; color: #0083B8;">Search Parameters</h3>
</div>
""", unsafe_allow_html=True)

# Input fields
col1, col2 = st.columns([1, 2])

with col1:
    search_type = st.selectbox(
        "Search Type",
        ["Business Name", "Document Number"]
    )

with col2:
    if search_type == "Business Name":
        search_term = st.text_input("Enter Business Name", placeholder="e.g., Acme Corporation")
    else:
        search_term = st.text_input("Enter Document Number", placeholder="e.g., L21000123456")

max_results = st.slider("Maximum Results to Scrape", min_value=1, max_value=50, value=10)

# Function to search Sunbiz using requests
def search_sunbiz(search_type, search_term, max_results, status_text, progress_bar):
    results = []
    
    # Set up headers to mimic a browser
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0'
    }
    
    try:
        # Navigate to the search page based on search type
        if search_type == "Business Name":
            status_text.text("Searching by business name...")
            search_url = "https://search.sunbiz.org/Inquiry/CorporationSearch/SearchResults/EntityName/" + search_term
            response = requests.get(search_url, headers=headers )
        else:
            # Document Number search
            status_text.text("Searching by document number...")
            search_url = "https://search.sunbiz.org/Inquiry/CorporationSearch/SearchResults/DocumentNumber/" + search_term
            response = requests.get(search_url, headers=headers )
        
        # Check if the request was successful
        if response.status_code != 200:
            return {"success": False, "message": f"Error: Received status code {response.status_code}"}
        
        # Parse the HTML content
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Check if we have results
        no_results = soup.find(string=re.compile("No Results Found")) or soup.find(string=re.compile("No records found"))
        if no_results:
            status_text.text("No results found")
            return {"success": False, "message": "No results found. Try a different search term."}
        
        # Find all search results
        result_links = []
        
        # Try different selectors for results
        search_results_table = soup.find('table', class_='search-results-table')
        if search_results_table:
            result_links = search_results_table.find_all('a')
        else:
            # Try alternative selectors
            result_links = soup.select('a.entity-name') or soup.select('table tr td:first-child a')
        
        if not result_links:
            return {"success": False, "message": "Could not find search results. The website structure may have changed."}
        
        # Process each result
        current_count = 0
        for i, link in enumerate(result_links):
            if current_count >= max_results:
                break
                
            # Update progress
            status_text.text(f"Processing: {current_count+1}/{max_results} businesses")
            progress_bar.progress((current_count+1) / max_results)
            
            # Get business name and URL
            business_name = link.text.strip()
            detail_url = link.get('href')
            if detail_url and not detail_url.startswith("http" ):
                detail_url = "https://search.sunbiz.org" + detail_url
            
            # Get status if available
            status = "Active"  # Default
            try:
                # Try to find status in the same row
                parent_row = link.find_parent('tr' )
                if parent_row:
                    status_cell = parent_row.find_all('td')
                    if len(status_cell) > 1:
                        status = status_cell[1].text.strip()
            except Exception:
                pass  # Use default status if not found
            
            # Get detail page
            try:
                detail_response = requests.get(detail_url, headers=headers)
                if detail_response.status_code == 200:
                    detail_soup = BeautifulSoup(detail_response.text, 'html.parser')
                    
                    # Extract business details
                    business_info = extract_business_details(detail_soup)
                    
                    # Add to results
                    results.append({
                        "Business Name": business_name,
                        "Status": status,
                        "Document Number": business_info.get("document_number", ""),
                        "FEI/EIN Number": business_info.get("fei_number", ""),
                        "Owner Name": business_info.get("owner_name", ""),
                        "Owner Title": business_info.get("owner_title", ""),
                        "Owner Email": business_info.get("owner_email", ""),
                        "Address": business_info.get("address", ""),
                        "Filing Date": business_info.get("filing_date", ""),
                        "Sunbiz URL": detail_url
                    })
                    
                    current_count += 1
                    
                    # Small delay to avoid aggressive scraping
                    time.sleep(1)
            except Exception as e:
                status_text.text(f"Error processing {business_name}: {str(e)}")
        
        return {"success": True, "data": results}
            
    except Exception as e:
        return {"success": False, "message": f"Error: {str(e)}"}

# Function to extract business details from detail page
def extract_business_details(soup):
    # Extract document number
    doc_number = ""
    doc_label = soup.find(string=re.compile("Document Number"))
    if doc_label:
        doc_element = doc_label.find_parent().find_next_sibling()
        if doc_element:
            doc_number = doc_element.text.strip()
    
    # Extract FEI/EIN Number
    fei_number = ""
    fei_label = soup.find(string=re.compile("FEI/EIN Number"))
    if fei_label:
        fei_element = fei_label.find_parent().find_next_sibling()
        if fei_element:
            fei_number = fei_element.text.strip()
    
    # Extract filing date
    filing_date = ""
    date_label = soup.find(string=re.compile("Date Filed"))
    if date_label:
        date_element = date_label.find_parent().find_next_sibling()
        if date_element:
            filing_date = date_element.text.strip()
    
    # Extract principal address
    address = ""
    address_label = soup.find(string=re.compile("Principal Address"))
    if address_label:
        address_element = address_label.find_parent()
        if address_element:
            next_elements = address_element.find_next_siblings()
            for element in next_elements:
                if "Mailing Address" in element.text or "Registered Agent" in element.text:
                    break
                if element.text.strip():
                    address += element.text.strip() + ", "
            address = address.rstrip(", ")
    
    # Extract owner information - prioritize President/CEO
    owner_name = ""
    owner_title = ""
    
    # Look for Officer/Director section
    officer_tables = soup.find_all('table')
    for table in officer_tables:
        rows = table.find_all('tr')
        
        # First look for President or CEO
        for row in rows:
            cells = row.find_all('td')
            if len(cells) >= 2:
                title = cells[1].text.lower()
                if "president" in title or "ceo" in title or "chief executive" in title:
                    owner_name = cells[0].text.strip()
                    owner_title = cells[1].text.strip()
                    break
        
        # If no President/CEO, take the first officer
        if not owner_name and rows:
            cells = rows[0].find_all('td')
            if len(cells) >= 2:
                owner_name = cells[0].text.strip()
                owner_title = cells[1].text.strip()
    
    # Extract email - look throughout the page
    owner_email = ""
    email_regex = r'[\w.+-]+@[\w-]+\.[\w.-]+'
    page_text = soup.get_text()
    email_matches = re.findall(email_regex, page_text)
    
    if email_matches:
        # Filter out common false positives
        filtered_emails = [email for email in email_matches if 
                          not email.endswith('@sunbiz.org') and 
                          not email.endswith('@dos.myflorida.com') and
                          not email.endswith('@leg.state.fl.us') and
                          not 'example.com' in email and
                          not 'domain.com' in email]
        
        if filtered_emails:
            owner_email = filtered_emails[0]
    
    return {
        "document_number": doc_number,
        "fei_number": fei_number,
        "owner_name": owner_name,
        "owner_title": owner_title,
        "owner_email": owner_email,
        "address": address,
        "filing_date": filing_date
    }

# Function to convert results to CSV
def convert_to_csv(data):
    # Create a DataFrame
    df = pd.DataFrame(data)
    
    # Handle any special characters or encoding issues
    for col in df.columns:
        df[col] = df[col].apply(lambda x: str(x).replace('\r', ' ').replace('\n', ' ') if pd.notnull(x) else '')
    
    # Convert to CSV
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False, quoting=csv.QUOTE_NONNUMERIC)
    return csv_buffer.getvalue()

# Function to convert results to Excel
def convert_to_excel(data):
    df = pd.DataFrame(data)
    excel_buffer = io.BytesIO()
    df.to_excel(excel_buffer, index=False, engine='openpyxl')
    excel_buffer.seek(0)
    return excel_buffer

# Create a card-like container for the button
st.markdown("""
<div style="background-color: #f8f9fa; padding: 1.5rem; border-radius: 8px; border: 1px solid #e9ecef; margin-bottom: 2rem;">
""", unsafe_allow_html=True)

# Create a button to start scraping
start_button = st.button("Start Scraping")

st.markdown("</div>", unsafe_allow_html=True)

# Initialize session state for results
if 'results' not in st.session_state:
    st.session_state.results = None

if start_button:
    if not search_term:
        st.error("Please enter a search term.")
    else:
        # Create a progress container
        progress_container = st.container()
        with progress_container:
            st.markdown("""
            <div style="background-color: #f8f9fa; padding: 1.5rem; border-radius: 8px; border: 1px solid #e9ecef; margin-bottom: 2rem;">
                <h3 style="margin-top: 0; color: #0083B8;">Scraping Progress</h3>
            """, unsafe_allow_html=True)
            
            # Create a progress bar and status text
            progress_bar = st.progress(0)
            status_text = st.empty()
            status_text.text("Starting search...")
            
            st.markdown("</div>", unsafe_allow_html=True)
        
        # Run the scraper
        results = search_sunbiz(search_type, search_term, max_results, status_text, progress_bar)
        
        # Reset progress indicators
        progress_container.empty()
        
        if results["success"]:
            st.session_state.results = results["data"]
            st.success(f"Found {len(results['data'])} businesses.")
        else:
            st.error(results["message"])

# Display results if available
if st.session_state.results:
    # Results container
    st.markdown("""
    <div style="background-color: #f8f9fa; padding: 1.5rem; border-radius: 8px; border: 1px solid #e9ecef; margin-bottom: 2rem;">
        <h3 style="margin-top: 0; color: #0083B8;">Search Results</h3>
    """, unsafe_allow_html=True)
    
    # Display as a table
    st.dataframe(st.session_state.results, use_container_width=True)
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Export container
    st.markdown("""
    <div style="background-color: #f8f9fa; padding: 1.5rem; border-radius: 8px; border: 1px solid #e9ecef; margin-bottom: 2rem;">
        <h3 style="margin-top: 0; color: #0083B8;">Export Options</h3>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    # CSV export
    with col1:
        csv_data = convert_to_csv(st.session_state.results)
        st.download_button(
            label="Download CSV",
            data=csv_data,
            file_name=f"sunbiz_results_{search_term.replace(' ', '_')}.csv",
            mime="text/csv",
            key="csv_download",
            help="Download results as CSV (compatible with Excel, Google Sheets, etc.)"
        )
    
    # Excel export
    with col2:
        excel_data = convert_to_excel(st.session_state.results)
        st.download_button(
            label="Download Excel",
            data=excel_data,
            file_name=f"sunbiz_results_{search_term.replace(' ', '_')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="excel_download",
            help="Download results as Excel spreadsheet"
        )
    
    st.markdown("</div>", unsafe_allow_html=True)

# Footer with disclaimer
st.markdown("---")
st.markdown("""
<div style="background-color: #f8f9fa; padding: 1rem; border-radius: 8px; border: 1px solid #e9ecef;">
    <h4 style="margin-top: 0; color: #0083B8;">About This Tool</h4>
    <p>This tool scrapes publicly available information from the Florida Department of State Division of Corporations website (Sunbiz.org).</p>
    <p><strong>Disclaimer:</strong> Please ensure your use complies with Sunbiz terms of service and applicable laws. This tool is for informational purposes only.</p>
</div>
""", unsafe_allow_html=True)
