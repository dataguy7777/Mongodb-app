# app.py

import streamlit as st
import pytesseract
from PIL import Image
import cv2
import numpy as np
import pandas as pd
from pymongo import MongoClient
from streamlit_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
import os

# ============================
# Configuration Section
# ============================

# MongoDB Configuration
# Replace the below URI with your actual MongoDB connection string.
# For example, if you're running MongoDB locally, it might be "mongodb://localhost:27017/"
MONGO_URI = "your_mongodb_connection_string"
DB_NAME = "receipt_db"
COLLECTION_NAME = "receipts"

# Tesseract OCR Configuration
# If Tesseract is not in your PATH, specify the full path to the executable.
# For example, on Windows:
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
# Uncomment and set the path if necessary.
# pytesseract.pytesseract.tesseract_cmd = r'/usr/local/bin/tesseract'

# ============================
# Initialize MongoDB Client
# ============================

try:
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]
    st.sidebar.success("Connected to MongoDB successfully!")
except Exception as e:
    st.sidebar.error(f"Error connecting to MongoDB: {e}")

# ============================
# Define OCR Function
# ============================

def ocr_core(image):
    """
    Perform OCR on the provided image and return extracted text.
    """
    # Convert PIL image to OpenCV format
    image = np.array(image)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Optional: Apply additional preprocessing steps if needed
    # Example: Thresholding to get a binary image
    gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    
    # Perform OCR
    custom_config = r'--oem 3 --psm 6'
    text = pytesseract.image_to_string(gray, config=custom_config)
    return text

# ============================
# Define Parsing Function
# ============================

def parse_receipt(text):
    """
    Parse the OCR extracted text and return structured data as a pandas DataFrame.
    This function assumes that each line contains a key-value pair separated by a colon (:).
    Modify this function based on your receipt format for better accuracy.
    """
    lines = text.split('\n')
    data = []
    for line in lines:
        if ':' in line:
            key, value = line.split(':', 1)
            data.append({"Field": key.strip(), "Value": value.strip()})
    # Convert to DataFrame
    df = pd.DataFrame(data)
    if df.empty:
        df = pd.DataFrame({"Field": [], "Value": []})
    return df

# ============================
# Streamlit App Interface
# ============================

def main():
    st.set_page_config(page_title="Receipt OCR App", layout="wide")
    st.title("🧾 Receipt OCR and Data Extraction App")

    st.markdown("""
    This application allows you to upload receipt images, extract text using OCR, edit the extracted data, and store it in a MongoDB database.
    """)

    # Sidebar for image upload
    st.sidebar.header("Upload Receipt Image")
    uploaded_file = st.sidebar.file_uploader("Choose an image...", type=["jpg", "jpeg", "png", "bmp", "tiff"])

    if uploaded_file is not None:
        # Display the uploaded image
        image = Image.open(uploaded_file)
        st.image(image, caption='Uploaded Receipt', use_column_width=True)
        
        # Perform OCR
        with st.spinner("Performing OCR..."):
            extracted_text = ocr_core(image)
        
        st.subheader("📄 Extracted Text")
        st.text_area("Extracted Text:", extracted_text, height=200)

        # Parse the text into structured data
        df = parse_receipt(extracted_text)
        
        if not df.empty:
            st.subheader("✏️ Editable Data Table")
            
            # Configure AgGrid
            gb = GridOptionsBuilder.from_dataframe(df)
            gb.configure_default_column(editable=True, sortable=True, filter=True)
            gb.configure_pagination(paginationAutoPageSize=True)
            gb.configure_side_bar()
            grid_options = gb.build()
            
            grid_response = AgGrid(
                df,
                gridOptions=grid_options,
                update_mode=GridUpdateMode.MODEL_CHANGED,
                allow_unsafe_jscode=True,
                theme='streamlit',  # Other themes: 'light', 'dark', 'material'
                height=400,
                width='100%',
            )
            
            updated_df = grid_response['data']
            
            if st.button("💾 Save to MongoDB"):
                # Convert DataFrame to Dictionary
                records = updated_df.to_dict(orient='records')
                try:
                    collection.insert_many(records)
                    st.success("✅ Data saved to MongoDB successfully!")
                except Exception as e:
                    st.error(f"❌ An error occurred while saving to MongoDB: {e}")
        else:
            st.warning("⚠️ No key-value pairs found in the extracted text. Please check the receipt format or improve the parsing logic.")

        # Optionally, display data from MongoDB
        if st.checkbox("🔍 Show Stored Data from MongoDB"):
            try:
                stored_data = list(collection.find())
                if stored_data:
                    # Remove MongoDB's default '_id' field for display purposes
                    for record in stored_data:
                        record.pop('_id', None)
                    stored_df = pd.DataFrame(stored_data)
                    st.dataframe(stored_df)
                else:
                    st.info("No data found in MongoDB.")
            except Exception as e:
                st.error(f"Error fetching data from MongoDB: {e}")

    else:
        st.info("📥 Please upload a receipt image to get started.")

    # Footer
    st.markdown("---")
    st.markdown("Developed with ❤️ using Streamlit, Tesseract OCR, and MongoDB.")

if __name__ == "__main__":
    main()