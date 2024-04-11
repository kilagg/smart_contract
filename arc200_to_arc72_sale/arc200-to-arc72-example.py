from time import time, sleep

from algosdk import account, encoding
from algosdk.logic import get_application_address
from algosdk import transaction
from ARC72.operations import create_ARC72_NFT, ARC72_Transfer
from ARC200.operations import create_ARC200_token, setupARC200App, ARC200_Transfer, ARC200_OptIn
from ARC200ARC72.operations import create_ARC200_ARC72Sale_App, setup_ARC200_ARC72Sale_App, Buy_ARC200_ARC72Sale, close_ARC200_ARC72Sale
from sale.operations import createSaleApp, setupSaleApp, Buy, closeSale, updateSalePrice
from sale.util import (
    getBalances,
    getAppGlobalState,
    getAppLocalState,
    getLastBlockTimestamp,waitForTransaction,
    to_algorand_address_style
)
from sale.testing.setup import getAlgodClient
from sale.testing.resources import (
    getTemporaryAccount,
    optInToAsset,
    createDummyAsset,
)
from sale.operations_test import *

def decode_dict_addresses(input_dict):
    """
    Decode byte sequence keys in a dictionary that are valid Algorand addresses to their human-readable form.
    Leave other keys as they are.
    """
    decoded_dict = {}
    for key, value in input_dict.items():
        # Check if the key is a byte sequence and of length 32 (Algorand public key length without checksum)
        if isinstance(key, bytes) and len(key) == 32:
            try:
                # Attempt to decode the Algorand address
                decoded_key = encoding.encode_address(key)
                decoded_dict[decoded_key] = value
            except Exception as e:
                # If decoding fails, leave the key as-is
                print(e)
                decoded_dict[key] = value
        else:
            # If the key is not a byte sequence or not of length 32, leave it as-is
            decoded_dict[key] = value
    return decoded_dict


def simple_sale():
    client = getAlgodClient()
    print("LETS GO")
    print("Generating temporary accounts...")
    creator = getTemporaryAccount(client)
    buyer = getTemporaryAccount(client)

    print("Bob (creator / seller account):", creator.getAddress())
    print("Carla (buyer account)", buyer.getAddress())
    
    creatorNftBalance = getBalances(client, creator.getAddress())
    buyerNftBalance = getBalances(client, buyer.getAddress())
    print("The creator holds now the following = ",creatorNftBalance)
    print("The buyer holds now the following = ",buyerNftBalance)

    nftID = 123456
    print("Parameter: NFT id = ",nftID)

    ###### ARC200 MINTING
    print("Bob is creating a ARC200 token contract..")
    ARC200AppID = create_ARC200_token(        
        client=client,
        sender=creator,
        total_supply_key=1000,
        decimals = 6,
        name = "test token",
        symbol = "TST"
    )

    print(
        "********\nThe ARC200 Token app ID is",
        ARC200AppID,
        "and the associated account is",
        get_application_address(ARC200AppID),
        "\n",
    )
    
    print("Bob is setting up the token...")
    setupARC200App(
        client=client,
        appID=ARC200AppID,
        sender=creator
    )
    print("Done. Supply is minted to Bob.")

    local_balance_data = getAppLocalState(client, ARC200AppID, creator)
    print("Let's check Bob balance:",local_balance_data)

    print("Now Alice opt in to the token")
    ARC200_OptIn(
        client=client,
        appID=ARC200AppID,
        sender=buyer
    )
    print("Bob nows sends 50 token to Alice")
    ARC200_Transfer(
        client=client,
        appID=ARC200AppID,
        sender=creator,
        receiver=buyer,
        amount=50
    )

    local_balance_data = getAppLocalState(client, ARC200AppID, creator)
    print("Let's check Bob balance:",local_balance_data)
    local_balance_data = getAppLocalState(client, ARC200AppID, buyer)
    print("Let's check Alice balance:",local_balance_data)

    ######################################

    ###### ARC72 MINTING
    print("Bob is creating a ARC72 NFT contract..")
    ARC72AppID = create_ARC72_NFT(
        client=client,
        sender=creator,
        nftID=nftID
    )
    print(
        "********\nThe ARC72 NFT app ID is",
        ARC72AppID,
        "and the associated account is",
        get_application_address(ARC72AppID),
        "\n",
    )
    owner_bytes = getAppGlobalState(client, ARC72AppID)[b"owner"]
    current_nft_owner = to_algorand_address_style(owner_bytes)
    print("Current NFT owner is = ", current_nft_owner[:5])

    startTime = int(time()) + 1  # start time is 1 seconds in the future
    price = 1000000

    print("Bob is creating the ARC200 Sale contract for his NFT App ID ",ARC72AppID," and NFT ID ",nftID)
    SaleAppID = create_ARC200_ARC72Sale_App(
        client=client,
        sender=creator,
        seller=creator.getAddress(),
        nftAppID=ARC72AppID,
        nftID=nftID,
        startTime=startTime,
        price=price,
        arc200_app_id=ARC200AppID
    )

    escrow_sale_contract = get_application_address(SaleAppID)
    print(
        "********\nThe ARC200->ARC720 sale app ID is",
        SaleAppID,
        "and the escrow account is",
        escrow_sale_contract,
        "\n",
    )

    print("Setup/funding the contract...")
    setup_ARC200_ARC72Sale_App(client=client, appID=SaleAppID, funder=creator)

    sleep(1)
    
    creatorNftBalance = getBalances(client, creator.getAddress())
    buyerNftBalance = getBalances(client, buyer.getAddress())
    escrow_sale_contractBalance = getBalances(client, escrow_sale_contract)
    print("The creator holds now the following = ",creatorNftBalance)
    print("The buyer holds now the following = ",buyerNftBalance)
    print("Sale Escrow ALGO balance =", escrow_sale_contractBalance)


    owner_bytes = getAppGlobalState(client, ARC72AppID)[b"owner"]
    print("Current NFT owner  is = ", to_algorand_address_style(owner_bytes)[:5])
    # simulate transfer() from Bob to Alice

    ###### ARC72 TRANSFER
    ##########################################################
    print("\nBob is transfering his NFT to the Sale contract by ARC72_Transfer")
    ARC72_Transfer(client=client, nft_app_id=ARC72AppID, sender=creator, receiver=escrow_sale_contract, nft_id=nftID)
    print("\n")
    owner_bytes = getAppGlobalState(client, ARC72AppID)[b"owner"]
    current_nft_owner = to_algorand_address_style(owner_bytes)
    print("Current NFT owner is = ", current_nft_owner[:5])

    # # now end the sale
    # print("Bob will now delete the Sale App")
    # close_ARC200_ARC72Sale(client=client, appID=SaleAppID, closer=creator)
    
    # owner_bytes = getAppGlobalState(client, ARC72AppID)[b"owner"]
    # print("Current NFT owner  is = ", to_algorand_address_style(owner_bytes)[:5])

    # print("End.")
    # exit(1)

    sellerBalancesBefore =  getBalances(client, creator.getAddress())
    print("Alice's balance:", sellerBalancesBefore)

    price = getAppGlobalState(client, SaleAppID)[b"price"]
    current_nft_price = price
    print("NFT onchain price  is = ", price)

    new_price = 50
    print("Updating price to allow Alice to buy in, and test the update function.")
    updateSalePrice(
        client= client,
        appID= SaleAppID,
        funder= creator,
        price= new_price,
    )
    current_nft_price = new_price
    print("\n")
    price = getAppGlobalState(client, SaleAppID)[b"price"]
    current_nft_price = price
    print("NFT onchain price  is = ", price)
    
    escrow_sale_contractBalance = getBalances(client, escrow_sale_contract)
    print("Sale Escrow ALGO balance =", escrow_sale_contractBalance)

    buyerBalancesBefore = getBalances(client, buyer.getAddress())
    buyerAlgosBefore = buyerBalancesBefore[0]
    print("Carla wants to buy the NFT, her balance:", buyerBalancesBefore)
    print("Carla is buying...")

    
    approval_state = getAppLocalState(client, ARC200AppID, buyer)
    print("Let's check SaleAppID allowance from buyer:",approval_state, "on app ")
    ##########################################################
    # Buy(client=client, appID=SaleAppID, nft_app_id=ARC72AppID, buyer=buyer, price=current_nft_price)
    try:
        Buy_ARC200_ARC72Sale(client=client, appID=SaleAppID, nft_app_id=ARC72AppID, arc200_app_id=ARC200AppID, buyer=buyer, price=current_nft_price)
    except Exception as e:
        print("Error during Buy_ARC200_ARC72Sale: ",e)

    approval_state = getAppLocalState(client, ARC200AppID, buyer)
    # Decode the dictionary
    decoded_dict = decode_dict_addresses(approval_state)
    print("\nLet's check SaleAppID allowance from buyer:",decoded_dict)
    sleep(2)
    owner_bytes = getAppGlobalState(client, ARC72AppID)[b"owner"]
    current_nft_owner = to_algorand_address_style(owner_bytes)
    print("Final NFT owner is = ", current_nft_owner[:5])

    
    bob_state = getAppLocalState(client, ARC200AppID, creator)
    decoded_dict = decode_dict_addresses(bob_state)
    print("Bob (seller) ARC200 balance:",decoded_dict)    
    alice_state = getAppLocalState(client, ARC200AppID, buyer)
    decoded_dict = decode_dict_addresses(alice_state)
    print("Alice (buyer) ARC200 balance:",decoded_dict)

    # now end the sale
    print("Bob will now delete the Sale App")
    close_ARC200_ARC72Sale(client=client, appID=SaleAppID, closer=creator)
    print("End.")

simple_sale()