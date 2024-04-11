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

def create_ARC200_token(
    client: AlgodClient,
    sender: Account,
    total_supply_key: int,
    decimals: int,
    name: str,
    symbol: str,
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
    localSchema = transaction.StateSchema(num_uints=2, num_byte_slices=2)

    app_args = []
    app_args.append( total_supply_key.to_bytes(8, "big") )
    app_args.append( decimals.to_bytes(8, "big") )
    app_args.append( name )
    app_args.append( symbol )


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

def setupARC200App(
    client: AlgodClient,
    appID: int,
    sender: Account
) -> None:
    """Finish setting up an auction.

    This operation funds the app auction escrow account, opts that account into
    the NFT, and sends the NFT to the escrow account, all in one atomic
    transaction group. The auction must not have started yet.

    The escrow account requires a total of 0.203 Algos for funding. See the code
    below for a breakdown of this amount.

    Args:
        client: An algod client.
        appID: The app ID of the auction.
        sender: The account setting up the ARC200 and receiving the total supply
    """
    appAddr = get_application_address(appID)

    suggestedParams = client.suggested_params()

    # Perform an opt-in transaction for the sender account
    opt_in_txn = transaction.ApplicationOptInTxn(sender.getAddress(), client.suggested_params(), appID)

    setupTxn = transaction.ApplicationCallTxn(
        sender=sender.getAddress(),
        index=appID,
        on_complete=transaction.OnComplete.NoOpOC,
        app_args=[b"setup"],
        sp=suggestedParams,
    )

    transaction.assign_group_id([opt_in_txn, setupTxn])

    signedOptInTxn = opt_in_txn.sign(sender.getPrivateKey())
    signedSetupTxn = setupTxn.sign(sender.getPrivateKey())

    client.send_transactions([signedOptInTxn, signedSetupTxn])
    waitForTransaction(client, signedSetupTxn.get_txid())


################################################################################
################


def ARC200_Transfer(client: AlgodClient, appID: int, sender:Account, receiver: Account, amount: int) -> None:
    """Call arc200_transfer on the NFT contract, must be from the owner

    Args:
        client: An Algod client.
        appID: The app ID of the ARC200 NFT.
        receiver: The account receiving the nft (becoming owner)
    """
    appAddr = get_application_address(appID)
    appGlobalState = getAppGlobalState(client, appID)

    # Args: 
    # arc200_transfer
    # receiver (bytes)
    # amount (bytes)
    app_args = [b"arc200_transfer"]
    # app_args.append(
    #     encoding.decode_address(sender.getAddress())
    # )
    if isinstance(receiver, str):
        receiver_str = receiver
        app_args.append(
            encoding.decode_address(receiver)
        )
    else:
        receiver_str = receiver.getAddress()
        app_args.append(
            encoding.decode_address(receiver.getAddress())
        )
        
    app_args.append(amount.to_bytes(8, "big"))

    suggestedParams = client.suggested_params()

    accounts: List[str] = [encoding.encode_address(appGlobalState[b"owner"])]
    # accounts.append(receiver.getAddress())

    if isinstance(receiver, str):
        accounts.append(
            receiver
        )
    else:
        accounts.append(
           receiver.getAddress()
        )

    print("ARC_200 call: app_args = ",[b"arc200_transfer", receiver_str, amount])

    appCallTxn = transaction.ApplicationCallTxn(
        sender=sender.getAddress(),
        index=appID,
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
    

def ARC200_OptIn(client: AlgodClient, appID: int, sender:Account) -> None:
    """Call arc200_transfer on the NFT contract, must be from the owner

    Args:
        client: An Algod client.
        appID: The app ID of the ARC200 NFT.
        receiver: The account receiving the nft (becoming owner)
    """
    appAddr = get_application_address(appID)

    suggestedParams = client.suggested_params()

    opt_in_txn = transaction.ApplicationOptInTxn(sender.getAddress(), client.suggested_params(), appID)

    signedOptInTxn = opt_in_txn.sign(sender.getPrivateKey())
    client.send_transaction(signedOptInTxn)
    waitForTransaction(client, signedOptInTxn.get_txid())