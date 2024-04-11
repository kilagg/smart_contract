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


def create_ARC200_ARC72Sale_App(
    client: AlgodClient,
    sender: Account,
    seller: str,
    nftAppID: int,
    nftID: int,
    startTime: int,
    price: int,
    arc200_app_id: int,
) -> int:
    """Create a new Sale.

    Args:
        client: An algod client.
        sender: The account that will create the Sale application.
        seller: The address of the seller that currently holds the NFT being
            auctioned.
        nftAppID: The ID of the NFT application.
        nftID: The ID of the NFT being auctioned.
        startTime: A UNIX timestamp representing the start time of the Sale.
            This must be greater than the current UNIX timestamp.
        price: The price of the NFT.
        arc200_app_id: The ID of the ARC-200 token application.

    Returns:
        The ID of the newly created Sale app.
    """
    approval, clear = getContracts(client)

    globalSchema = transaction.StateSchema(num_uints=8, num_byte_slices=8)
    localSchema = transaction.StateSchema(num_uints=0, num_byte_slices=0)

    app_args = [
        encoding.decode_address(seller),
        nftAppID.to_bytes(8, "big"),
        nftID.to_bytes(8, "big"),
        startTime.to_bytes(8, "big"),
        price.to_bytes(8, "big"),
        arc200_app_id.to_bytes(8, "big"),
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


def setup_ARC200_ARC72Sale_App(

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
        400_000+ 10_000
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


    updateTxn = transaction.ApplicationCallTxn(
        sender=funder.getAddress(),
        index=appID,
        on_complete=transaction.OnComplete.NoOpOC,
        app_args=app_args,
        sp=suggestedParams,
    )

    signedupdateTxn = updateTxn.sign(funder.getPrivateKey())

    client.send_transactions([signedupdateTxn])

    waitForTransaction(client, signedupdateTxn.get_txid())



def Buy_ARC200_ARC72Sale(client: AlgodClient, appID: int, nft_app_id: int, arc200_app_id, buyer: Account, price: int) -> None:
    """Place a bid on an active Sale.

    Args:
        client: An Algod client.
        appID: The app ID of the Sale.
        buyer: The account providing the bid.
        price: The amount of the bid.
    """
    appAddr = get_application_address(appID)
    print("Buying:\t-appAddr = ",appAddr," with ", price,"  ARC200")
    appGlobalState = getAppGlobalState(client, appID)

    nftID = appGlobalState[b"nft_id"]

    suggestedParams = client.suggested_params()
    # First transaction: Buyer approves the Sale contract to spend `price` amount of ARC-200 tokens
    app_args_ = [b"arc200_approve", encoding.decode_address(appAddr), price.to_bytes(8, "big")]
    print("Approve Token ARC200 tx: ",[b"arc200_approve", appAddr, price])
    approve_txn = transaction.ApplicationCallTxn(
        sender=buyer.getAddress(),
        index=arc200_app_id,
        on_complete=transaction.OnComplete.NoOpOC,
        app_args=app_args_,
        sp=suggestedParams,
    )
    
    # signedPayTxn = approve_txn.sign(buyer.getPrivateKey())
    # client.send_transaction(signedPayTxn)
    # waitForTransaction(client, signedPayTxn.get_txid())
    # print("Approve done.")

    foreign_apps = [arc200_app_id,nft_app_id]
    foreign_accounts: List[str] = [encoding.encode_address(appGlobalState[b"seller"])]    
    foreign_accounts.append(buyer.getAddress())
    # print("Foreign accounts = ",foreign_accounts)
    # Second transaction: Buy call to the Sale contract
    buy_txn = transaction.ApplicationCallTxn(
        sender=buyer.getAddress(),
        index=appID,
        on_complete=transaction.OnComplete.NoOpOC,
        app_args=[b"buy"],
        accounts=foreign_accounts,
        foreign_apps=foreign_apps,
        sp=suggestedParams,
    )
    print("Buy on ARC200>ARC72 Sale App tx: ",[b"buy", appID, price])

    transaction.assign_group_id([approve_txn, buy_txn])
    signedPayTxn = approve_txn.sign(buyer.getPrivateKey())
    signedAppCallTxn = buy_txn.sign(buyer.getPrivateKey())
    client.send_transactions([signedPayTxn, signedAppCallTxn])
    waitForTransaction(client, signedAppCallTxn.get_txid())


def cancelSale(
    client: AlgodClient,
    appID: int
) -> None:
    """Finish setting up an Sale.

    """
    suggestedParams = client.suggested_params()

    app_args =[b"cancel"]
    accounts: List[str] = [encoding.encode_address(appGlobalState[b"seller"])]
    foreign_apps = [appGlobalState[b"arc200_app_id"], appGlobalState[b"nft_app_id"]]

    updateTxn = transaction.ApplicationCallTxn(
        sender=funder.getAddress(),
        index=appID,
        on_complete=transaction.OnComplete.NoOpOC,
        app_args=app_args,
        foreign_apps=foreign_apps,
        accounts=accounts,
        sp=suggestedParams,
    )

    signedupdateTxn = updateTxn.sign(funder.getPrivateKey())

    client.send_transactions([signedupdateTxn])

    waitForTransaction(client, signedupdateTxn.get_txid())



def close_ARC200_ARC72Sale(client: AlgodClient, appID: int, closer: Account) -> None:
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
    foreign_apps = [appGlobalState[b"arc200_app_id"], appGlobalState[b"nft_app_id"]]
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
