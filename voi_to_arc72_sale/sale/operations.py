from typing import Tuple, List

from algosdk.v2client.algod import AlgodClient
from algosdk import transaction
from algosdk.logic import get_application_address
from algosdk import account, encoding

from pyteal import compileTeal, Mode

from .account import Account
from .contracts import approval_program, clear_state_program
from .util import (
    waitForTransaction,
    fullyCompileContract,
    getAppGlobalState,
)

APPROVAL_PROGRAM = b""
CLEAR_STATE_PROGRAM = b""


def getContracts(client: AlgodClient) -> Tuple[bytes, bytes]:
    """Get the compiled TEAL contracts for the Sale.

    Args:
        client: An algod client that has the ability to compile TEAL programs.

    Returns:
        A tuple of 2 byte strings. The first is the approval program, and the
        second is the clear state program.
    """
    global APPROVAL_PROGRAM
    global CLEAR_STATE_PROGRAM

    if len(APPROVAL_PROGRAM) == 0:
        APPROVAL_PROGRAM = fullyCompileContract(client, approval_program())
        CLEAR_STATE_PROGRAM = fullyCompileContract(client, clear_state_program())

    return APPROVAL_PROGRAM, CLEAR_STATE_PROGRAM


def createSaleApp(
    client: AlgodClient,
    sender: Account,
    seller: str,
    nftAppID: int,
    nftID: int,
    price: int,
    fees_address: str
) -> int:
    """Create a new Sale.

    Args:
        client: An algod client.
        sender: The account that will create the Sale application.
        seller: The address of the seller that currently holds the NFT being
            auctioned.
        nftID: The ID of the NFT being auctioned.
        reserve: The reserve amount of the Sale. If the Sale ends without
            a bid that is equal to or greater than this amount, the Sale will
            fail, meaning the bid amount will be refunded to the lead bidder and
            the NFT will return to the seller.
        minBidIncrement: The minimum different required between a new bid and
            the current leading bid.

    Returns:
        The ID of the newly created Sale app.
    """
    approval, clear = getContracts(client)

    globalSchema = transaction.StateSchema(num_uints=7, num_byte_slices=7)
    localSchema = transaction.StateSchema(num_uints=0, num_byte_slices=0)

    app_args = [
        encoding.decode_address(seller),
        nftAppID.to_bytes(8, "big"),
        nftID.to_bytes(8, "big"),
        price.to_bytes(8, "big"),
        encoding.decode_address(fees_address)
    ]

    txn = transaction.ApplicationCreateTxn(
        sender=sender.getAddress(),
        on_complete=transaction.OnComplete.NoOpOC,
        approval_program=approval,
        clear_program=clear,
        global_schema=globalSchema,
        local_schema=localSchema,
        app_args=app_args,
        sp=client.suggested_params(),
    )

    signedTxn = txn.sign(sender.getPrivateKey())

    client.send_transaction(signedTxn)

    response = waitForTransaction(client, signedTxn.get_txid())
    assert response.applicationIndex is not None and response.applicationIndex > 0
    return response.applicationIndex


def setupSaleApp(
    client: AlgodClient,
    appID: int,
    funder: Account,
) -> None:
    """Finish setting up an Sale.

    This operation funds the app Sale escrow account, opts that account into
    the NFT, and sends the NFT to the escrow account, all in one atomic
    transaction group. The Sale must not have started yet.

    The escrow account requires a total of 0.203 Algos for funding. See the code
    below for a breakdown of this amount.

    Args:
        client: An algod client.
        appID: The app ID of the Sale.
        funder: The account providing the funding for the escrow account.
        nftID: The NFT ID
    """
    appAddr = get_application_address(appID)

    suggestedParams = client.suggested_params()

    fundingAmount = (
        # min account balance
        100_000+ 10_000
    )

    fundAppTxn = transaction.PaymentTxn(
        sender=funder.getAddress(),
        receiver=appAddr,
        amt=fundingAmount,
        sp=suggestedParams,
    )

    transaction.assign_group_id([fundAppTxn])

    signedFundAppTxn = fundAppTxn.sign(funder.getPrivateKey())
    client.send_transactions([signedFundAppTxn])
    waitForTransaction(client, signedFundAppTxn.get_txid())


def updateSalePrice(
    client: AlgodClient,
    appID: int,
    funder: Account,
    price: int,
) -> None:
    """Finish setting up an Sale.

    """
    suggestedParams = client.suggested_params()

    app_args =[b"update_price"]
    app_args.append( (price.to_bytes(8, "big")) )

    appGlobalState = getAppGlobalState(client, appID)
    accounts: List[str] = [encoding.encode_address(appGlobalState[b"fees_address"])]    
    # or replace directly from function input

    # forge tx
    updateTxn = transaction.ApplicationCallTxn(
        sender=funder.getAddress(),
        index=appID,
        on_complete=transaction.OnComplete.NoOpOC,
        app_args=app_args,
        accounts=accounts,
        sp=suggestedParams,
    )

    signedupdateTxn = updateTxn.sign(funder.getPrivateKey())

    client.send_transactions([signedupdateTxn])

    waitForTransaction(client, signedupdateTxn.get_txid())


def get_nft_id_box(nft_id):
    hex_nft = hex(nft_id)[2:]
    value = 0
    padding = 64 - len(hex_nft)
    hex_nft_n = f"6e{value:#0{padding}}{hex_nft}"
    return bytes.fromhex(hex_nft_n)


def get_double_address_box(address):
    hex_address = encoding.decode_address(address).hex()
    return bytes.fromhex(hex_address + hex_address)


def get_address_box(address):
    hex_address = encoding.decode_address(address).hex()
    return bytes.fromhex('62' + hex_address)


def Buy(client: AlgodClient, appID: int, nft_app_id: int, buyer: Account, price: int) -> None:
    """Place a bid on an active Sale.

    Args:
        client: An Algod client.
        appID: The app ID of the Sale.
        buyer: The account providing the bid.
        price: The amount of the bid.
    """
    appAddr = get_application_address(appID)
    print("Buying:\t-appAddr = ",appAddr," with ",price," algo")
    appGlobalState = getAppGlobalState(client, appID)

    # Also possible to provide directly as parameters, attention with encoding.
    nftID = appGlobalState[b"nft_id"] # ref 
    seller_address = encoding.encode_address(appGlobalState[b"seller"])
    fees_address = encoding.encode_address(appGlobalState[b"fees_address"])

    suggestedParams = client.suggested_params()

    # Pre-Validation Transaction (Transaction 1)
    # Unique references: 5
    # - Buyer's address (ref 1)
    # - Sale application ID (ref 2)
    # - Seller's address (ref 3)
    # - Fees address (ref 4)
    # - NFT application ID (ref 5)
    preValidateTxn = transaction.ApplicationCallTxn(
        sender=buyer.getAddress(),
        index=appID,
        on_complete=transaction.OnComplete.NoOpOC,
        app_args=[b"pre_validate"],
        accounts=[seller_address, fees_address],
        foreign_apps=[nft_app_id],
        sp=suggestedParams,
    )

    # Payment Transaction (Transaction 2)
    # Unique references: 2
    # - Buyer's address (ref 1, shared with preValidateTxn)
    # - Application's address (ref 6)
    payTxn = transaction.PaymentTxn(
        sender=buyer.getAddress(),
        receiver=appAddr,
        amt=price,
        sp=suggestedParams,
    )

    # Application Call Transaction (Transaction 3)
    # Unique references: 6
    # - Buyer's address (ref 1, shared with preValidateTxn and payTxn)
    # - Sale application ID (ref 2, implicitly included at position 0)
    # - NFT ID box (ref 7)
    # - Buyer's address duplication box (ref 8)
    # - Buyer's address box (ref 9)
    # - Application's address box (ref 10)
    appCallTxn = transaction.ApplicationCallTxn(
        sender=buyer.getAddress(),
        index=appID,
        on_complete=transaction.OnComplete.NoOpOC,
        app_args=[b"buy"],
        sp=suggestedParams,
        boxes=[(0, get_nft_id_box(nftID)),
            (0, get_double_address_box(buyer.getAddress())),
            (0, get_address_box(buyer.getAddress())),
            (0, get_address_box(appAddr)),
            ],
    )
    print("---------- \nSigning the grouped preValidate - Fund - Buy transaction")

    # Group the transactions
    grouped_txns = [preValidateTxn, payTxn, appCallTxn]
    transaction.assign_group_id(grouped_txns)

    # Sign the transactions
    signedPreValidateTxn = preValidateTxn.sign(buyer.getPrivateKey())
    signedPayTxn = payTxn.sign(buyer.getPrivateKey())
    signedAppCallTxn = appCallTxn.sign(buyer.getPrivateKey())

    # Send the transactions
    try:
        client.send_transactions([signedPreValidateTxn, signedPayTxn, signedAppCallTxn])
        waitForTransaction(client, appCallTxn.get_txid())
        print("<*>\tTransaction passed\n----------")
    except Exception as e:
        print("<!>\tTransaction Failed: ",e,"\n----------")


def closeSale(client: AlgodClient, appID: int, closer: Account):
    """Close an Sale.

    This action can only happen before an Sale has begun, in which case it is
    cancelled, or after an Sale has ended.

    If called after the Sale has ended and the Sale was successful, the
    NFT is transferred to the winning bidder and the Sale proceeds are
    transferred to the seller. If the Sale was not successful, the NFT and
    all funds are transferred to the seller.

    Args:
        client: An Algod client.
        appID: The app ID of the Sale.
        closer: The account initiating the close transaction. This must be
            either the seller or Sale creator if you wish to close the
            Sale before it starts. Otherwise, this can be any account.
    """
    appGlobalState = getAppGlobalState(client, appID)

    nftID = appGlobalState[b"nft_id"]

    accounts: List[str] = [encoding.encode_address(appGlobalState[b"seller"])]

    foreign_apps = [appGlobalState[b"nft_app_id"]]
    deleteTxn = transaction.ApplicationDeleteTxn(
        sender=closer.getAddress(),
        index=appID,
        accounts=accounts,
        foreign_apps=foreign_apps,
        sp=client.suggested_params(),
    )
    signedDeleteTxn = deleteTxn.sign(closer.getPrivateKey())

    client.send_transaction(signedDeleteTxn)

    waitForTransaction(client, signedDeleteTxn.get_txid())
