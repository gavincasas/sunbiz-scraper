import streamlit as st
import pandas as pd
import time
import re
import io
import csv
from playwright.sync_api import sync_playwright
# Configure Playwright to run without sandbox
import os
os.environ["PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD"] = "1"
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "/opt/render/.cache/ms-playwright"

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
    .stAlert {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 4px;
    }
    .download-btn {
        background-color: #28a745;
        color: white;
        font-weight: 500;
    }
    .stDataFrame {
        border: 1px solid #e9ecef;
        border-radius: 5px;
        padding: 1rem;
    }
    .stTextInput>div>div>input {
        border-radius: 4px;
        border: 1px solid #ced4da;
        padding: 0.5rem;
    }
    .stSelectbox>div>div>div {
        border-radius: 4px;
        border: 1px solid #ced4da;
    }
    .stCaption {
        font-size: 0.8rem;
        color: #6c757d;
    }
    .css-1d391kg {
        padding-top: 3rem;
    }
    .block-container {
        max-width: 1000px;
        padding-top: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# App header
st.title("Sunbiz Business Owner Scraper")
st.markdown("Extract business owner information from Florida's Sunbiz registry and export to CSV or Excel.")

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

# Function to scrape Sunbiz using Playwright
def search_sunbiz(search_type, search_term, max_results, status_text, progress_bar):
    results = []
    
    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True), args=['--no-sandbox'])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
        page = context.new_page()
        
        try:
            # Navigate to the search page based on search type
            if search_type == "Business Name":
                status_text.text("Navigating to Sunbiz search page...")
                page.goto("https://search.sunbiz.org/Inquiry/CorporationSearch/ByName", timeout=30000)
                
                # Fill in the search form
                status_text.text(f"Searching for: {search_term}")
                page.fill("#SearchTerm", search_term)
                page.click("input[type='submit']")
            else:
                # Document Number search
                status_text.text("Navigating to Sunbiz search page...")
                page.goto("https://search.sunbiz.org/Inquiry/CorporationSearch/SearchResults/DocumentNumber/" + search_term, timeout=30000)
            
            # Wait for results to load
            status_text.text("Waiting for search results...")
            try:
                # Try multiple possible selectors for search results
                page.wait_for_selector("table.search-results-table, div.searchResultsList, div.search-results, table tr td a", timeout=30000)
            except Exception as e:
                status_text.text(f"Warning: Could not find standard results container: {str(e)}")
                # Wait for any content to load
                page.wait_for_load_state("networkidle", timeout=30000)
            
            # Check if we have results
            no_results_text = page.content()
            if "No Results Found" in no_results_text or "No records found" in no_results_text:
                status_text.text("No results found")
                browser.close()
                return {"success": False, "message": "No results found. Try a different search term."}
            
            # Process all pages of results until we reach max_results
            current_count = 0
            current_page = 1
            
            while current_count < max_results:
                status_text.text(f"Processing page {current_page} of results...")
                
                # Get all search results on current page
                result_links = []
                
                # Try different selectors for results
                for selector in [
                    "a.entity-name",
                    "table.search-results-table a",
                    "div.searchResultsList a",
                    "table tr td:first-child a",
                    "table a[href*='SearchResultDetail']"
                ]:
                    result_links = page.query_selector_all(selector)
                    if result_links and len(result_links) > 0:
                        status_text.text(f"Found {len(result_links)} results on page {current_page} with selector: {selector}")
                        break
                
                if not result_links or len(result_links) == 0:
                    if current_page == 1:
                        status_text.text("Could not find any search results")
                        browser.close()
                        return {"success": False, "message": "No results found. Try a different search term."}
                    else:
                        # We've processed all pages
                        break
                
                # Process each result on this page
                for i, link in enumerate(result_links):
                    if current_count >= max_results:
                        break
                        
                    # Update progress
                    status_text.text(f"Processing: {current_count+1}/{max_results} businesses")
                    progress_bar.progress((current_count+1) / max_results)
                    
                    # Get business name and URL
                    business_name = link.inner_text().strip()
                    detail_url = link.get_attribute("href")
                    if detail_url and not detail_url.startswith("http"):
                        detail_url = "https://search.sunbiz.org" + detail_url
                    
                    # Get status if available
                    status = "Active"  # Default
                    try:
                        # Try to find status in the same row
                        row = link.evaluate("node => node.closest('tr')")
                        if row:
                            status_cell = page.evaluate("""row => {
                                const cells = row.querySelectorAll('td');
                                return cells.length > 1 ? cells[1].innerText.trim() : null;
                            }""", row)
                            if status_cell:
                                status = status_cell
                    except Exception:
                        pass  # Use default status if not found
                    
                    # Open detail page in new tab
                    page_detail = context.new_page()
                    try:
                        page_detail.goto(detail_url, timeout=30000)
                        page_detail.wait_for_load_state("networkidle", timeout=30000)
                        
                        # Extract business details
                        business_info = extract_business_details(page_detail)
                        
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
                        
                        # Close detail page
                        page_detail.close()
                        
                        # Small delay to avoid aggressive scraping
                        time.sleep(0.5)
                        
                    except Exception as e:
                        status_text.text(f"Error processing {business_name}: {str(e)}")
                        page_detail.close()
                
                # Check if we need to go to next page and if there is one
                if current_count < max_results:
                    # Look for next page link
                    next_page = None
                    for selector in [
                        "a.navigationLink:has-text('Next')",
                        "a:has-text('Next')",
                        "a[href*='Page']:has-text('Next')"
                    ]:
                        next_page = page.query_selector(selector)
                        if next_page:
                            break
                    
                    if next_page:
                        status_text.text(f"Moving to page {current_page + 1}...")
                        next_page.click()
                        page.wait_for_load_state("networkidle", timeout=30000)
                        current_page += 1
                    else:
                        # No more pages
                        break
                else:
                    # We've reached max_results
                    break
            
            browser.close()
            return {"success": True, "data": results}
            
        except Exception as e:
            browser.close()
            return {"success": False, "message": f"Error: {str(e)}"}

# Function to extract business details from detail page
def extract_business_details(page):
    # Extract document number
    doc_number = page.evaluate("""() => {
        const docLabel = Array.from(document.querySelectorAll('label, div, span')).find(el => 
            el.innerText && el.innerText.includes('Document Number'));
        if (docLabel) {
            const next = docLabel.nextElementSibling;
            return next ? next.innerText.trim() : '';
        }
        return '';
    }""")
    
    # Extract FEI/EIN Number
    fei_number = page.evaluate("""() => {
        const feiLabel = Array.from(document.querySelectorAll('label, div, span')).find(el => 
            el.innerText && el.innerText.includes('FEI/EIN Number'));
        if (feiLabel) {
            const next = feiLabel.nextElementSibling;
            return next ? next.innerText.trim() : '';
        }
        return '';
    }""")
    
    # Extract filing date
    filing_date = page.evaluate("""() => {
        const dateLabel = Array.from(document.querySelectorAll('label, div, span')).find(el => 
            el.innerText && el.innerText.includes('Date Filed'));
        if (dateLabel) {
            const next = dateLabel.nextElementSibling;
            return next ? next.innerText.trim() : '';
        }
        return '';
    }""")
    
    # Extract principal address
    address = page.evaluate("""() => {
        const addressLabel = Array.from(document.querySelectorAll('label, div, span')).find(el => 
            el.innerText && el.innerText.includes('Principal Address'));
        if (addressLabel) {
            let result = '';
            let current = addressLabel.nextElementSibling;
            while (current && !current.innerText.includes('Mailing Address') && 
                  !current.innerText.includes('Registered Agent')) {
                if (current.innerText.trim()) {
                    result += current.innerText.trim() + ', ';
                }
                current = current.nextElementSibling;
            }
            return result.replace(/,\\s*$/, '');
        }
        return '';
    }""")
    
    # Extract owner information - prioritize President/CEO
    owner_info = page.evaluate("""() => {
        let ownerName = '';
        let ownerTitle = '';
        
        // First check Officer/Director Detail section
        const officerSection = Array.from(document.querySelectorAll('div, span, h2, h3')).find(el => 
            el.innerText && el.innerText.includes('Officer/Director Detail'));
        
        if (officerSection) {
            // Find all tables that might contain officer info
            const tables = Array.from(document.querySelectorAll('table'));
            for (const table of tables) {
                const rows = Array.from(table.querySelectorAll('tr'));
                
                // First look for President or CEO
                for (const row of rows) {
                    const cells = Array.from(row.querySelectorAll('td'));
                    if (cells.length >= 2) {
                        const title = cells[1].innerText.toLowerCase();
                        if (title.includes('president') || title.includes('ceo') || 
                            title.includes('chief executive')) {
                            return {
                                name: cells[0].innerText.trim(),
                                title: cells[1].innerText.trim()
                            };
                        }
                    }
                }
                
                // If no President/CEO, take the first officer
                if (rows.length > 0) {
                    const cells = Array.from(rows[0].querySelectorAll('td'));
                    if (cells.length >= 2) {
                        return {
                            name: cells[0].innerText.trim(),
                            title: cells[1].innerText.trim()
                        };
                    }
                }
            }
        }
        
        // Also check for Authorized Person(s) Detail section
        const authorizedSection = Array.from(document.querySelectorAll('div, span, h2, h3')).find(el => 
            el.innerText && el.innerText.includes('Authorized Person'));
        
        if (authorizedSection) {
            // Find all tables that might contain authorized person info
            const tables = Array.from(document.querySelectorAll('table'));
            for (const table of tables) {
                const rows = Array.from(table.querySelectorAll('tr'));
                
                // First look for Manager or Managing Member
                for (const row of rows) {
                    const cells = Array.from(row.querySelectorAll('td'));
                    if (cells.length >= 2) {
                        const title = cells[1].innerText.toLowerCase();
                        if (title.includes('manager') || title.includes('managing member')) {
                            return {
                                name: cells[0].innerText.trim(),
                                title: cells[1].innerText.trim()
                            };
                        }
                    }
                }
                
                // If no Manager, take the first authorized person
                if (rows.length > 0) {
                    const cells = Array.from(rows[0].querySelectorAll('td'));
                    if (cells.length >= 2) {
                        return {
                            name: cells[0].innerText.trim(),
                            title: cells[1].innerText.trim()
                        };
                    }
                }
            }
        }
        
        // If no officers or authorized persons found, try Registered Agent
        const agentSection = Array.from(document.querySelectorAll('div, span, h2, h3')).find(el => 
            el.innerText && el.innerText.includes('Registered Agent'));
        
        if (agentSection) {
            let current = agentSection.nextElementSibling;
            while (current && current.innerText && 
                  !current.innerText.includes('Officer/Director') &&
                  !current.innerText.includes('Authorized Person')) {
                const text = current.innerText.trim();
                if (text && text !== 'Name & Address') {
                    // Take the first line as the name
                    const lines = text.split('\\n');
                    return {
                        name: lines[0].trim(),
                        title: 'Registered Agent'
                    };
                }
                current = current.nextElementSibling;
            }
        }
        
        return { name: '', title: '' };
    }""")
    
    # Extract email - look throughout the page with improved regex
    owner_email = page.evaluate("""() => {
        // More comprehensive email regex that handles various formats
        const emailRegex = /[\\w.\\-+]+@[\\w\\-]+\\.[\\w\\-.]+/g;
        const pageText = document.body.innerText;
        const matches = pageText.match(emailRegex);
        
        if (matches && matches.length > 0) {
            // Filter out common false positives
            const filtered = matches.filter(email => 
                !email.endsWith('@sunbiz.org') && 
                !email.endsWith('@dos.myflorida.com') &&
                !email.endsWith('@leg.state.fl.us') &&
                !email.includes('example.com') &&
                !email.includes('domain.com'));
            
            return filtered.length > 0 ? filtered[0] : '';
        }
        
        return '';
    }""")
    
    return {
        "document_number": doc_number,
        "fei_number": fei_number,
        "owner_name": owner_info.get("name", ""),
        "owner_title": owner_info.get("title", ""),
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
    <p><strong>Features:</strong></p>
    <ul>
        <li>Search by business name or document number</li>
        <li>Extract business owner names and contact information</li>
        <li>Export data to CSV or Excel format</li>
        <li>Clean, minimal interface for easy use</li>
    </ul>
    <p><strong>Disclaimer:</strong> Please ensure your use complies with Sunbiz terms of service and applicable laws. This tool is for informational purposes only.</p>
</div>
""", unsafe_allow_html=True)
