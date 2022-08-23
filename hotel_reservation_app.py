import os
import json
from web3 import Web3
from pathlib import Path
from dotenv import load_dotenv
import streamlit as st
from PIL import Image
import time
import pandas as pd
import requests

from pinata import pin_file_to_ipfs, pin_json_to_ipfs, convert_data_to_json

from functions import get_location, get_hotels

load_dotenv()

# A-  Create an instance of web3.py for communication to the Blockchain smart contract
w3 = Web3(Web3.HTTPProvider(os.getenv("WEB3_PROVIDER_URI")))


# B- loading the saved contract data (ABI file) and smart contract address that deployed the contract  / Needed for the front-end interaction with the back-end (Using Web3 to connect to the contract)


@st.cache(allow_output_mutation=True)
def load_contract():

    # Load the contract ABI
    with open(Path("./contracts/compiled/hotel_reservation_registry_abi.json")) as f:
        contract_abi = json.load(f)

    # Set the contract address (this is the address of the deployed contract)
    contract_address = os.getenv("SMART_CONTRACT_ADDRESS")

    # Calling the contract
    contract = w3.eth.contract(address=contract_address, abi=contract_abi)

    return contract


contract = load_contract()

# C- Helper functions to pin files and json to Pinata


def pin_hotel_reservation(hotel_name, hotel_confirmation_file):
    # Pin the file to IPFS with Pinata
    ipfs_file_hash = pin_file_to_ipfs(hotel_confirmation_file.getvalue())

    # Build a token metadata file for the Hotel Reservation
    token_json = {"name": hotel_name, "image": ipfs_file_hash}
    json_data = convert_data_to_json(token_json)

    # Pin the json to IPFS with Pinata
    json_ipfs_hash = pin_json_to_ipfs(json_data)

    return json_ipfs_hash


def pin_historical_price_report(report_content):
    json_report = convert_data_to_json(report_content)
    report_ipfs_hash = pin_json_to_ipfs(json_report)
    return report_ipfs_hash


# Ca- Function to display background image from a URL for frontend User friendly visualization


def add_bg_from_url():

    st.markdown(
        f"""
        <style>
        .stApp {{
            background-image: url("https://cdn.galaxy.tf/unit-media/tc-default/uploads/images/room_photo/001/597/271/king-room-resort-tower-1600x1067-wide.jpg");
            background-attachement: fixed;
            background-size: cover
        }} 

        </style>
        """,
        unsafe_allow_html=True,
    )


add_bg_from_url()

# D-  Minting/Tokenizing the Hotel Reservations

st.title("Hotel Reservation NFT System")

# Create blank dataframes for Streamlit
hotel_price_df = pd.DataFrame()
selectable_hotel_dict = {}

# Room input details
city = st.text_input('Which city would you like to search?')
col1top, col2top = st.columns(2)
with col1top:
    checkin_date = st.date_input('Check-In')
with col2top:
    checkout_date = st.date_input('Check-Out')

col1bottom, col2bottom = st.columns(2)
with col1bottom:
    adults_number = st.number_input('Number of Adults', min_value = 1, step=1)
with col2bottom:
    room_number = st.number_input('Number of Rooms', min_value = 1, step=1)


# Format the values
adults_number = str(adults_number)
room_number = str(room_number)
checkin_date = str(checkin_date)
checkout_date = str(checkout_date)


# Search Locations
if st.checkbox('Set Location'):
    destination_id = get_location(city)


# Search hotels
if st.checkbox('Search'):
    hotel_response = get_hotels(destination_id, checkin_date, checkout_date, adults_number, room_number)


# Checkbox to display the dataframe
if st.checkbox('Display Dataframe'):
    st.text('List Ordered by Popularity')
    hotel_data = hotel_response.json()

    # Create empty lists for json values to be populated in
    hotel_list = []
    total_price_list = []
    average_price_list = []
    picklist_label = []

    # Loop through all queried hotels in a given page to populate the values in the lists
    i = 0
    while i < 20:
        hotel_list.append(hotel_data['result'][i]['hotel_name'])
        total_price_list.append(hotel_data['result'][i]['price_breakdown']['all_inclusive_price'])
        average_price_list.append(hotel_data['result'][i]['composite_price_breakdown']['gross_amount_per_night']['value'])
        picklist_label.append(hotel_data['result'][i]['hotel_name'] + ' - $' + str(round(hotel_data['result'][i]['composite_price_breakdown']['gross_amount_per_night']['value'],2)) + ' per night - $' + str(round(hotel_data['result'][i]['price_breakdown']['all_inclusive_price'],2)) + ' total cost')
        i += 1

    # Create the final hotel list as a list of lists
    final_hotel_list = [hotel_list, average_price_list, total_price_list]
    selectable_hotel_dict = dict(zip(hotel_list, picklist_label))

    # Create the hotel price dataframe
    hotel_price_df = pd.DataFrame(final_hotel_list).transpose()
    hotel_price_df.columns = ['Hotel Name', 'Average Price', 'Total Price']
    hotel_price_df = hotel_price_df.set_index('Hotel Name')

# Set chosen values
chosen_hotel = st.selectbox('Select a Hotel', selectable_hotel_dict, format_func = lambda x: selectable_hotel_dict.get(x))
chosen_average_price = hotel_price_df.loc[chosen_hotel , 'Average Price']
chosen_total_price = hotel_price_df.loc[chosen_hotel , 'Total Price']

accounts = w3.eth.accounts
if st.checkbox("Do you want to Tokenize your Reservation at this time"):
    st.write("Input an account to get started")
    address = st.text_input("Input Account Address")
    st.markdown("---")

    st.markdown("## Tokenize Hotel Reservation")
    hotel_name = st.text(chosen_hotel)
    hotel_room_value = st.text(chosen_total_price)
    hotel_confirmation = st.text_input("Enter the reservation confirmation")
    file = st.file_uploader("Upload Confirmation Receipt")
    if st.button("Tokenize Hotel Reservation"):
        # Use the `pin_hotel_reservation` helper function to pin the file to IPFS
        hotel_reservation_ipfs_hash = pin_hotel_reservation(hotel_name, file)
        hotel_reservation_uri = f"ipfs://{hotel_reservation_ipfs_hash}"
        tx_hash = contract.functions.registerHotelReservation(
            address,
            hotel_name,
            str(checkin_date),
            str(checkout_date),
            str(hotel_confirmation),
            int(hotel_room_value),
            hotel_reservation_uri,
        ).transact({"from": address, "gas": 1000000})
        with st.spinner("Tokenizing Reservation ..."):
            time.sleep(10)
        st.success("Success!")
        st.balloons()
        receipt = w3.eth.waitForTransactionReceipt(tx_hash)
        st.write("Transaction receipt mined:")
        st.write(dict(receipt))
        st.write(
            "You can view the pinned metadata file with the following IPFS Gateway Link"
        )
        st.markdown(
            f"[Hotel Reservation IPFS Gateway Link](https://ipfs.io/ipfs/{hotel_reservation_ipfs_hash})"
        )
    st.markdown("---")


# F- Updated Price for Hotel Reservation Token/NFT

st.markdown("## Current Price of Tokenized IDs")
if st.checkbox(
    "Do you want to see the current market value of your Tokenized IDs at this time"
):
    tokens = contract.functions.totalSupply().call()
    token_id = st.selectbox("Choose a Reservation Token ID", list(range(tokens)))
    current_price = contract.functions.roomconfirmation(token_id).call()[-1]
    st.text(f" Current Price on BlockChain $ {current_price}")
    # .call("hotelRoomValue"))
    updated_room_price = st.text_input(
        "API Call for updated room price"
    )  # **Will update functionality - An API call will be made to get updated Price**
    updated_price_report = f"Updated Price on ?today's date: {updated_room_price} "  # **Need to update code to put the current date when ever function is called**
    if st.button("Update Price on BlockChain"):

        # Use Pinata to pin an updated price report for the report URI
        updated_price_report_ipfs_hash = pin_historical_price_report(
            updated_price_report
        )
        report_uri = f"ipfs://{updated_price_report_ipfs_hash}"

        # Use the token_id and the report_uri to record the updated price of token/nft
        tx_hash = contract.functions.updatedPriceOfReservation(
            token_id, int(updated_room_price), report_uri
        ).transact({"from": w3.eth.accounts[0]})
        receipt = w3.eth.waitForTransactionReceipt(tx_hash)
        st.write(receipt)
    st.markdown("---")

    # G- Get Historical Price Report

    st.markdown("## Get the Historical Price Log")
    historical_token_id = st.selectbox("Reservation Token ID", list(range(tokens)))
    if st.button("Get Price Log"):
        price_filter = contract.events.Price.createFilter(
            fromBlock="0x0", argument_filters={"token_id": historical_token_id}
        )
        reports = price_filter.get_all_entries()
        if reports:
            for report in reports:
                report_dictionary = dict(report)
                st.markdown("### Price Report Event Log")
                st.write(report_dictionary)
                st.markdown("### Pinata IPFS Report URI")
                report_uri = report_dictionary["args"]["reportURI"]
                report_ipfs_hash = report_uri[7:]
                st.markdown(
                    f"The report is located at the following URI: " f"{report_uri}"
                )
                st.write(
                    "You can also view the report URI with the following ipfs gateway link"
                )
                st.markdown(
                    f"[IPFS Gateway Link](https://ipfs.io/ipfs/{report_ipfs_hash})"
                )
                st.markdown("### Price Log Details")
                st.write(
                    pd.DataFrame(
                        [
                            str(report_dictionary["args"]["token_id"]),
                            str(report_dictionary["args"]["hotelRoomValue"]),
                            report_dictionary["args"]["reportURI"],
                        ],
                        index=["token_id", "hotelRoomValue", "reportURI"],
                    )
                )
        else:
            st.write("This reservation token ID has no new pricing")
