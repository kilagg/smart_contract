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

################
################################################################################
################

def getContracts(client: AlgodClient) -> Tuple[bytes, bytes]:
    """Get the compiled TEAL contracts for the Offer.

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


################
################################################################################
################

def create_ARC72_NFT(
    client: AlgodClient,
    sender: Account,
    nftID: int
) -> int:
    """Create a new Offer.

    Args:
        client: An algod client.
        sender: The account that will create the Offer application.
        seller: The address of the seller that currently holds the NFT being
            auctioned.
        nftIDs: The IDs of the NFTs being auctioned.
        endTime: A UNIX timestamp representing the end time of the Offer. This
            must be greater than startTime.
        reserve: The reserve amount of the Offer. If the Offer ends without
            a bid that is equal to or greater than this amount, the Offer will
            fail, meaning the bid amount will be refunded to the lead bidder and
            the NFT will return to the seller.
        minBidIncrement: The minimum different required between a new bid and
            the current leading bid.

    Returns:
        The ID of the newly created Offer app.
    """

    approval, clear = getContracts(client)

    # increase the num of variables with each N > 2
    base_u = 8
    base_slice = 7
    globalSchema = transaction.StateSchema(num_uints=base_u, num_byte_slices=base_slice)
    localSchema = transaction.StateSchema(num_uints=0, num_byte_slices=0)

    app_args = [nftID]
    # app_args.append( nftID.to_bytes(8, "big") )


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

################
################################################################################
################


def ARC72_Transfer(client: AlgodClient, nft_app_id: int, sender:Account, receiver: Account, nft_id: int) -> None:
    """Call arc72_transfer on the NFT contract, must be from the owner

    Args:
        client: An Algod client.
        appID: The app ID of the ARC72 NFT.
        receiver: The account receiving the nft (becoming owner)
    """
    appAddr = get_application_address(nft_app_id)
    appGlobalState = getAppGlobalState(client, nft_app_id)

    app_args = [b"arc72_transferFrom"]
    app_args.append(
        encoding.decode_address(sender.getAddress())
    )
    if isinstance(receiver, str):
        app_args.append(
            encoding.decode_address(receiver)
        )
    else:
        app_args.append(
            encoding.decode_address(receiver.getAddress())
        )
    app_args.append(nft_id)
    # app_args.append(receiver.getAddress())

    suggestedParams = client.suggested_params()

    accounts: List[str] = [encoding.encode_address(appGlobalState[b"owner"])]
    # accounts.append(receiver.getAddress())

    if isinstance(receiver, str):
        receiver_str = receiver
    else:
        receiver_str = receiver.getAddress()

    app_args.append(
        receiver_str
    )
    print("ARC_72 call: app_args = ",[b"arc72_transferFrom", sender.getAddress(), receiver_str, nft_id," on ",nft_app_id])

    appCallTxn = transaction.ApplicationCallTxn(
        sender=sender.getAddress(),
        index=nft_app_id,
        on_complete=transaction.OnComplete.NoOpOC,
        app_args=app_args,
        accounts=accounts,
        sp=suggestedParams,
    )
    print("Signing ApplicationCallTxn from Sender:",sender.getAddress())
    signedAppCallTxn = appCallTxn.sign(sender.getPrivateKey())
    print("broadcasting...")
    client.send_transaction(signedAppCallTxn)
    waitForTransaction(client, appCallTxn.get_txid())
    
################
################################################################################
################

def close_ARC72_NFT(client: AlgodClient, appID: int, closer: Account, nftID):
    """Close an Offer.

    This action can only happen before an Offer has begun, in which case it is
    cancelled, or after an Offer has ended.

    If called after the Offer has ended and the Offer was successful, the
    NFT is transferred to the winning bidder and the Offer proceeds are
    transferred to the seller. If the Offer was not successful, the NFT and
    all funds are transferred to the seller.

    Args:
        client: An Algod client.
        appID: The app ID of the Offer.
        closer: The account initiating the close transaction. This must be
            either the seller or Offer creator if you wish to close the
            Offer before it starts. Otherwise, this can be any account.
    """
    appGlobalState = getAppGlobalState(client, appID)


    accounts: List[str] = [encoding.encode_address(appGlobalState[b"buyer"])]

    if (b"seller" in appGlobalState):
        accounts.append(encoding.encode_address(appGlobalState[b"seller"]))

    deleteTxn = transaction.ApplicationDeleteTxn(
        sender=closer.getAddress(),
        index=appID,
        accounts=accounts,
        foreign_assets=[nftID],
        sp=client.suggested_params(),
    )
    signedDeleteTxn = deleteTxn.sign(closer.getPrivateKey())

    client.send_transaction(signedDeleteTxn)

    waitForTransaction(client, signedDeleteTxn.get_txid())
