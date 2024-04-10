from time import time, sleep

from algosdk import account, encoding
from algosdk.logic import get_application_address
from algosdk import transaction
from ARC72.operations import create_ARC72_NFT, ARC72_Transfer
from sale.operations import createSaleApp, setupSaleApp, Buy, closeSale, updateSalePrice
from sale.util import (
    getBalances,
    getAppGlobalState,
    getLastBlockTimestamp, waitForTransaction,
    to_algorand_address_style
)
from sale.testing.setup import getAlgodClient
from algosdk.v2client.indexer import IndexerClient

from sale.testing.resources import (
    getTemporaryAccount,
    optInToAsset,
    createDummyAsset,
)
from sale.operations_test import *


def simple_sale():
    client = getAlgodClient()
    indexer_client = IndexerClient("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                                   "http://localhost:4001")

    print("Generating temporary accounts...")
    creator = getTemporaryAccount(client)
    buyer = getTemporaryAccount(client)
    fees_address = getTemporaryAccount(client)

    print("Bob (creator / seller account):", creator.getAddress())
    print("Carla (buyer account)", buyer.getAddress())
    print("Fees (fees account)", fees_address.getAddress())

    creatorNftBalance = getBalances(client, creator.getAddress())
    buyerNftBalance = getBalances(client, buyer.getAddress())
    feesBalance = getBalances(client, fees_address.getAddress())
    print("The creator holds now the following = ", creatorNftBalance)
    print("The buyer holds now the following = ", buyerNftBalance)
    print("The fees holds now the following = ", feesBalance)

    nftID = 123456
    print("Parameter: NFT id = ", nftID)

    print("Bob is creating a ARC72 NFT contract..")
    ###### ARC72 MINTING
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

    price = 1000000

    print("Bob is creating the Sale contract for his NFT App ID ", ARC72AppID, " and NFT ID ", nftID)
    SaleAppID = createSaleApp(
        client=client,
        sender=creator,
        seller=creator.getAddress(),
        nftAppID=ARC72AppID,
        nftID=nftID,
        price=price,
        fees_address=fees_address.getAddress()
    )

    escrow_sale_contract = get_application_address(SaleAppID)
    print(
        "The ALGO->ARC720 sale app ID is",
        SaleAppID,
        "and the escrow account is",
        escrow_sale_contract,
        "\n",
    )

    print("Setup/funding the contract...")
    setupSaleApp(client=client, appID=SaleAppID, funder=creator)
    sleep(3)

    creatorNftBalance = getBalances(client, creator.getAddress())
    buyerNftBalance = getBalances(client, buyer.getAddress())
    escrow_sale_contractBalance = getBalances(client, escrow_sale_contract)
    print("The creator holds now the following = ", creatorNftBalance)
    print("The buyer holds now the following = ", buyerNftBalance)
    print("Sale Escrow ALGO balance =", escrow_sale_contractBalance)

    owner_bytes = getAppGlobalState(client, ARC72AppID)[b"owner"]
    print("Current NFT owner  is = ", to_algorand_address_style(owner_bytes)[:5])
    # simulate transfer() from Bob to Alice

    ###### ARC72 TRANSFER
    print("Bob is transfering his NFT to the Sale contract by ARC72_Transfer")
    ##########################################################
    ARC72_Transfer(client=client, nft_app_id=ARC72AppID, sender=creator, receiver=escrow_sale_contract, nft_id=nftID)
    print("\n")
    owner_bytes = getAppGlobalState(client, ARC72AppID)[b"owner"]
    current_nft_owner = to_algorand_address_style(owner_bytes)
    print("Current NFT owner is = ", current_nft_owner[:5])

    sellerBalancesBefore = getBalances(client, creator.getAddress())
    print("Alice's balance:", sellerBalancesBefore)

    price = getAppGlobalState(client, SaleAppID)[b"price"]
    current_nft_price = price
    print("NFT onchain price  is = ", price)

    new_price = 50000000
    print("Updating price just to test")
    updateSalePrice(
        client=client,
        appID=SaleAppID,
        funder=creator,
        price=new_price,
        fees_address=fees_address.getAddress(),
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

    ##########################################################
    Buy(client=client, appID=SaleAppID, nft_app_id=ARC72AppID, buyer=buyer, price=current_nft_price, fees_address=fees_address.getAddress())
    print("\n")

    sleep(3)
    escrow_sale_contractBalance = getBalances(client, escrow_sale_contract)
    print("Sale Escrow ALGO balance =", escrow_sale_contractBalance)

    buyerBalancesBefore = getBalances(client, buyer.getAddress())
    print("Carla balances:", buyerBalancesBefore)

    owner_bytes = getAppGlobalState(client, ARC72AppID)[b"owner"]
    current_nft_owner = to_algorand_address_style(owner_bytes)
    print("Final NFT owner is = ", current_nft_owner[:5])

    creatorNftBalance = getBalances(client, creator.getAddress())
    buyerNftBalance = getBalances(client, buyer.getAddress())
    print("The creator holds now the following = ", creatorNftBalance)
    print("The buyer holds now the following = ", buyerNftBalance)
    print("And now Alice transfers it back to Bob. Bob wins.")
    ARC72_Transfer(client=client, nft_app_id=ARC72AppID, sender=buyer, receiver=creator, nft_id=nftID)
    sleep(3)
    owner_bytes = getAppGlobalState(client, ARC72AppID)[b"owner"]
    current_nft_owner = to_algorand_address_style(owner_bytes)
    print("Current NFT owner is = ", current_nft_owner[:5])


simple_sale()