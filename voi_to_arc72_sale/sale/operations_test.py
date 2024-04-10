from time import time, sleep

import pytest

from algosdk import account, encoding
from algosdk.logic import get_application_address

from .operations import createSaleApp, setupSaleApp, Buy, closeSale
from .util import getBalances, getAppGlobalState, getLastBlockTimestamp
from .testing.setup import getAlgodClient
from .testing.resources import getTemporaryAccount, optInToAsset, createDummyAsset


def test_create():
    client = getAlgodClient()

    creator = getTemporaryAccount(client)
    _, seller_addr = account.generate_account()  # random address

    nftID = 1  # fake ID
    startTime = int(time()) + 10  # start time is 10 seconds in the future
    endTime = startTime + 60  # end time is 1 minute after start
    reserve = 1_000_000  # 1 Algo
    increment = 10  # 0.1 Algo

    
    gems_fees_acc = getTemporaryAccount(client)
    royalties_fees_acc = getTemporaryAccount(client)
    gems_fees_percentage = 5
    royalties_fees_percentage = 10
    late_bidding_delay = 10 # seconds

    appID = createSaleApp(
        client=client,
        sender=creator,
        seller=seller_addr,
        nftID=nftID,
        startTime=startTime,
        endTime=endTime,
        reserve=reserve,
        minBidIncrement=increment,
        gems_fees_wallet= gems_fees_acc.getAddress(),
        royalties_wallet= royalties_fees_acc.getAddress(),
        gems_fees_percent= gems_fees_percentage,
        royalties_fees_percent= royalties_fees_percentage,
        late_bidding_delay= late_bidding_delay
    )
    

    actual = getAppGlobalState(client, appID)
    expected = {
        b"seller": encoding.decode_address(seller_addr),
        b"nft_id": nftID,
        b"start": startTime,
        b"end": endTime,
        b"reserve_amount": reserve,
        b"min_bid_inc": increment,
        b"bid_account": bytes(32),  # decoded zero address
    }

    assert actual == expected


def test_setup():
    client = getAlgodClient()

    creator = getTemporaryAccount(client)
    seller = getTemporaryAccount(client)

    nftAmount = 1
    nftID = createDummyAsset(client, nftAmount, seller)

    startTime = int(time()) + 10  # start time is 10 seconds in the future
    endTime = startTime + 60  # end time is 1 minute after start
    reserve = 1_000_000  # 1 Algo
    increment = 10  # 0.1 Algo

    gems_fees_acc = getTemporaryAccount(client)
    royalties_fees_acc = getTemporaryAccount(client)
    gems_fees_percentage = 5
    royalties_fees_percentage = 10
    late_bidding_delay = 10 # seconds

    appID = createSaleApp(
        client=client,
        sender=creator,
        seller=seller.getAddress(),
        nftID=nftID,
        startTime=startTime,
        endTime=endTime,
        reserve=reserve,
        minBidIncrement=increment,
        gems_fees_wallet= gems_fees_acc.getAddress(),
        royalties_wallet= royalties_fees_acc.getAddress(),
        gems_fees_percent= gems_fees_percentage,
        royalties_fees_percent= royalties_fees_percentage,
        late_bidding_delay= late_bidding_delay
    )

    setupSaleApp(
        client=client,
        appID=appID,
        funder=creator,
        nftHolder=seller,
        nftID=nftID,
        nftAmount=nftAmount,
    )

    actualState = getAppGlobalState(client, appID)
    expectedState = {
        b"seller": encoding.decode_address(seller.getAddress()),
        b"nft_id": nftID,
        b"start": startTime,
        b"end": endTime,
        b"reserve_amount": reserve,
        b"min_bid_inc": increment,
        b"bid_account": bytes(32),  # decoded zero address
    }

    assert actualState == expectedState

    actualBalances = getBalances(client, get_application_address(appID))
    expectedBalances = {0: 2 * 10 + 2 * 1_000, nftID: nftAmount}

    # assert actualBalances == expectedBalances


def test_first_bid_before_start():
    client = getAlgodClient()

    creator = getTemporaryAccount(client)
    seller = getTemporaryAccount(client)

    nftAmount = 1
    print("create nft to Sale...")
    nftID = createDummyAsset(client, nftAmount, seller)
    print("start in 5min")
    startTime = int(time()) + 5 * 60  # start time is 5 minutes in the future
    endTime = startTime + 60  # end time is 1 minute after start
    reserve = 1_000_000  # 1 Algo
    increment = 10  # 0.1 Algo

    gems_fees_acc = getTemporaryAccount(client)
    royalties_fees_acc = getTemporaryAccount(client)
    gems_fees_percentage = 5
    royalties_fees_percentage = 10
    late_bidding_delay = 10 # seconds

    appID = createSaleApp(
        client=client,
        sender=creator,
        seller=seller.getAddress(),
        nftID=nftID,
        startTime=startTime,
        endTime=endTime,
        reserve=reserve,
        minBidIncrement=increment,
        gems_fees_wallet= gems_fees_acc.getAddress(),
        royalties_wallet= royalties_fees_acc.getAddress(),
        gems_fees_percent= gems_fees_percentage,
        royalties_fees_percent= royalties_fees_percentage,
        late_bidding_delay= late_bidding_delay
    )

    print("setup Sale")
    setupSaleApp(
        client=client,
        appID=appID,
        funder=creator,
        nftHolder=seller,
        nftID=nftID,
        nftAmount=nftAmount,
    )

    bidder = getTemporaryAccount(client)
    
    bidderNftBalance = getBalances(client, bidder.getAddress())
    print("The bidder holds the following = ",bidderNftBalance)    


    _, lastRoundTime = getLastBlockTimestamp(client)
    assert lastRoundTime < startTime

    print("bid too early on Sale")
    with pytest.raises(Exception):
        bidAmount = 500_000  # 0.5 Algos
        print("bid...")
        placeBid(client=client, appID=appID, bidder=bidder, bidAmount=bidAmount)
        print("Done")
    
    bidderNftBalance = getBalances(client, bidder.getAddress())
    print("The bidder holds now the following = ",bidderNftBalance)    
    actualAppBalances = getBalances(client, get_application_address(appID))
    print("The Sale escrow now holds the following:", actualAppBalances)
    print("End")


def test_first_bid():
    client = getAlgodClient()

    creator = getTemporaryAccount(client)
    seller = getTemporaryAccount(client)

    nftAmount = 1
    nftID = createDummyAsset(client, nftAmount, seller)

    startTime = int(time()) + 10  # start time is 10 seconds in the future
    endTime = startTime + 60  # end time is 1 minute after start
    reserve = 1_000_000  # 1 Algo
    increment = 10  # 0.1 Algo

    gems_fees_acc = getTemporaryAccount(client)
    royalties_fees_acc = getTemporaryAccount(client)
    gems_fees_percentage = 5
    royalties_fees_percentage = 10
    late_bidding_delay = 10 # seconds

    appID = createSaleApp(
        client=client,
        sender=creator,
        seller=seller.getAddress(),
        nftID=nftID,
        startTime=startTime,
        endTime=endTime,
        reserve=reserve,
        minBidIncrement=increment,
        gems_fees_wallet= gems_fees_acc.getAddress(),
        royalties_wallet= royalties_fees_acc.getAddress(),
        gems_fees_percent= gems_fees_percentage,
        royalties_fees_percent= royalties_fees_percentage,
        late_bidding_delay= late_bidding_delay
    )

    setupSaleApp(
        client=client,
        appID=appID,
        funder=creator,
        nftHolder=seller,
        nftID=nftID,
        nftAmount=nftAmount,
    )

    bidder = getTemporaryAccount(client)

    _, lastRoundTime = getLastBlockTimestamp(client)
    if lastRoundTime < startTime + 5:
        sleep(startTime + 5 - lastRoundTime)

    bidAmount = 500_000  # 0.5 Algos
    placeBid(client=client, appID=appID, bidder=bidder, bidAmount=bidAmount)

    actualState = getAppGlobalState(client, appID)
    expectedState = {
        b"seller": encoding.decode_address(seller.getAddress()),
        b"nft_id": nftID,
        b"start": startTime,
        b"end": endTime,
        b"reserve_amount": reserve,
        b"min_bid_inc": increment,
        b"num_bids": 1,
        b"bid_amount": bidAmount,
        b"bid_account": encoding.decode_address(bidder.getAddress()),
    }

    assert actualState == expectedState

    actualBalances = getBalances(client, get_application_address(appID))
    expectedBalances = {0: 2 * 10 + 2 * 1_000 + bidAmount, nftID: nftAmount}

    assert actualBalances == expectedBalances


def test_second_bid():
    client = getAlgodClient()

    creator = getTemporaryAccount(client)
    seller = getTemporaryAccount(client)

    nftAmount = 1
    nftID = createDummyAsset(client, nftAmount, seller)

    startTime = int(time()) + 10  # start time is 10 seconds in the future
    endTime = startTime + 60  # end time is 1 minute after start
    reserve = 1_000_000  # 1 Algo
    increment = 10  # 0.1 Algo

    gems_fees_acc = getTemporaryAccount(client)
    royalties_fees_acc = getTemporaryAccount(client)
    gems_fees_percentage = 5
    royalties_fees_percentage = 10
    late_bidding_delay = 10 # seconds

    appID = createSaleApp(
        client=client,
        sender=creator,
        seller=seller.getAddress(),
        nftID=nftID,
        startTime=startTime,
        endTime=endTime,
        reserve=reserve,
        minBidIncrement=increment,
        gems_fees_wallet= gems_fees_acc.getAddress(),
        royalties_wallet= royalties_fees_acc.getAddress(),
        gems_fees_percent= gems_fees_percentage,
        royalties_fees_percent= royalties_fees_percentage,
        late_bidding_delay= late_bidding_delay
    )

    setupSaleApp(
        client=client,
        appID=appID,
        funder=creator,
        nftHolder=seller,
        nftID=nftID,
        nftAmount=nftAmount,
    )

    bidder1 = getTemporaryAccount(client)
    bidder2 = getTemporaryAccount(client)

    _, lastRoundTime = getLastBlockTimestamp(client)
    if lastRoundTime < startTime + 5:
        sleep(startTime + 5 - lastRoundTime)

    bid1Amount = 500_000  # 0.5 Algos
    placeBid(client=client, appID=appID, bidder=bidder1, bidAmount=bid1Amount)

    bidder1AlgosBefore = getBalances(client, bidder1.getAddress())[0]

    with pytest.raises(Exception):
        bid2Amount = bid1Amount + 1_000  # increase is less than min increment amount
        placeBid(
            client=client,
            appID=appID,
            bidder=bidder2,
            bidAmount=bid2Amount,
        )

    bid2Amount = bid1Amount + increment
    placeBid(client=client, appID=appID, bidder=bidder2, bidAmount=bid2Amount)

    actualState = getAppGlobalState(client, appID)
    expectedState = {
        b"seller": encoding.decode_address(seller.getAddress()),
        b"nft_id": nftID,
        b"start": startTime,
        b"end": endTime,
        b"reserve_amount": reserve,
        b"min_bid_inc": increment,
        b"num_bids": 2,
        b"bid_amount": bid2Amount,
        b"bid_account": encoding.decode_address(bidder2.getAddress()),
    }

    assert actualState == expectedState

    actualAppBalances = getBalances(client, get_application_address(appID))
    expectedAppBalances = {0: 2 * 10 + 2 * 1_000 + bid2Amount, nftID: nftAmount}

    assert actualAppBalances == expectedAppBalances

    bidder1AlgosAfter = getBalances(client, bidder1.getAddress())[0]

    # bidder1 should receive a refund of their bid, minus the txn fee
    assert bidder1AlgosAfter - bidder1AlgosBefore >= bid1Amount - 1_000


def test_close_before_start():
    client = getAlgodClient()

    creator = getTemporaryAccount(client)
    seller = getTemporaryAccount(client)

    nftAmount = 1
    nftID = createDummyAsset(client, nftAmount, seller)

    startTime = int(time()) + 5 * 60  # start time is 5 minutes in the future
    endTime = startTime + 60  # end time is 1 minute after start
    reserve = 1_000_000  # 1 Algo
    increment = 10  # 0.1 Algo

    gems_fees_acc = getTemporaryAccount(client)
    royalties_fees_acc = getTemporaryAccount(client)
    gems_fees_percentage = 5
    royalties_fees_percentage = 10
    late_bidding_delay = 10 # seconds

    appID = createSaleApp(
        client=client,
        sender=creator,
        seller=seller.getAddress(),
        nftID=nftID,
        startTime=startTime,
        endTime=endTime,
        reserve=reserve,
        minBidIncrement=increment,
        gems_fees_wallet= gems_fees_acc.getAddress(),
        royalties_wallet= royalties_fees_acc.getAddress(),
        gems_fees_percent= gems_fees_percentage,
        royalties_fees_percent= royalties_fees_percentage,
        late_bidding_delay= late_bidding_delay
    )
    #
    setupSaleApp(
        client=client,
        appID=appID,
        funder=creator,
        nftHolder=seller,
        nftID=nftID,
        nftAmount=nftAmount,
    )

    _, lastRoundTime = getLastBlockTimestamp(client)
    assert lastRoundTime < startTime

    closeSale(client, appID, seller)

    actualAppBalances = getBalances(client, get_application_address(appID))
    expectedAppBalances = {0: 0}

    assert actualAppBalances == expectedAppBalances

    sellerNftBalance = getBalances(client, seller.getAddress())[nftID]
    assert sellerNftBalance == nftAmount



def test_close_after_start():
    client = getAlgodClient()

    creator = getTemporaryAccount(client)
    seller = getTemporaryAccount(client)


    print("Alice (seller account):", seller.getAddress())
    print("Bob (Sale creator account):", creator.getAddress())


    print("Alice is generating an example NFT...")
    nftAmount = 1
    nftID = createDummyAsset(client, nftAmount, seller)    
    print("The NFT ID is", nftID)

    startTime = int(time()) + 20  # start time is 20s in the future
    endTime = startTime + 60*3  # end time is 5 minute after start
    reserve = 10000  # 1 Algo
    increment = 10  # 0.1 Algo

    gems_fees_acc = getTemporaryAccount(client)
    royalties_fees_acc = getTemporaryAccount(client)
    gems_fees_percentage = 0
    royalties_fees_percentage = 0
    late_bidding_delay = 10 # seconds

    appID = createSaleApp(
        client=client,
        sender=creator,
        seller=seller.getAddress(),
        nftID=nftID,
        startTime=startTime,
        endTime=endTime,
        reserve=reserve,
        minBidIncrement=increment,
        gems_fees_wallet= gems_fees_acc.getAddress(),
        royalties_wallet= royalties_fees_acc.getAddress(),
        gems_fees_percent= gems_fees_percentage,
        royalties_fees_percent= royalties_fees_percentage,
        late_bidding_delay= late_bidding_delay
    )

    print("Setting up Sale app...")

    setupSaleApp(
        client=client,
        appID=appID,
        funder=creator,
        nftHolder=seller,
        nftID=nftID,
        nftAmount=nftAmount,
    )
    actualAppBalances = getBalances(client, get_application_address(appID))
    print("The Sale escrow now holds the following:", actualAppBalances)

    _, lastRoundTime = getLastBlockTimestamp(client)
    assert lastRoundTime < startTime

    print("Closing up Sale app")
    closeSale(client, appID, seller)

    actualAppBalances = getBalances(client, get_application_address(appID))
    print("The Sale escrow now holds the following:", actualAppBalances)
    expectedAppBalances = {0: 0}

    assert actualAppBalances == expectedAppBalances

    sellerNftBalance = getBalances(client, seller.getAddress())
    print("The seller now holds the following:", sellerNftBalance)
    assert sellerNftBalance[nftID] == nftAmount



def test_cancel_close_after_bids():
    client = getAlgodClient()

    print("Generating temporary accounts...")
    creator = getTemporaryAccount(client)
    seller = getTemporaryAccount(client)
    bidder = getTemporaryAccount(client)
    bidder2 = getTemporaryAccount(client)

    print("Alice (seller account):", seller.getAddress())
    print("Bob (Sale creator account):", creator.getAddress())
    print("Carla (bidder account)", bidder.getAddress())
    print("Math (bidder2 account)", bidder2.getAddress(), "\n")

    print("Alice is generating an example NFT...")
    nftAmount = 1
    nftID = createDummyAsset(client, nftAmount, seller)
    print("The NFT ID is", nftID)
    print("Alice's balances:", getBalances(client, seller.getAddress()), "\n")

    duration = 60*5 # in seconds
    startTime = int(time()) + 10  # start time is 10 seconds in the future
    endTime = startTime + duration  # end time is 5 mins  after start
    reserve = 1_000_000  # 1 Algo
    increment = 10  # 0.1 Algo
    
    gems_fees_acc = getTemporaryAccount(client)
    royalties_fees_acc = getTemporaryAccount(client)
    gems_fees_percentage = 5
    royalties_fees_percentage = 10
    late_bidding_delay = 10 # seconds

    print("Bob is creating an Sale that lasts {} seconds to Sale off the NFT...".format(str(duration)))
    appID = createSaleApp(
        client=client,
        sender=creator,
        seller=seller.getAddress(),
        nftID=nftID,
        startTime=startTime,
        endTime=endTime,
        reserve=reserve,
        minBidIncrement=increment,
        gems_fees_wallet= gems_fees_acc.getAddress(),
        royalties_wallet= royalties_fees_acc.getAddress(),
        gems_fees_percent= gems_fees_percentage,
        royalties_fees_percent= royalties_fees_percentage,
        late_bidding_delay= late_bidding_delay
    )
    print(
        "Done. The Sale app ID is",
        appID,
        "and the escrow account is",
        get_application_address(appID),
        "\n",
    )

    print("Alice is setting up and funding NFT Sale...")
    setupSaleApp(
        client=client,
        appID=appID,
        funder=seller,
        nftHolder=seller,
        nftID=nftID,
        nftAmount=nftAmount,
    )
    print("Done\n")

    sellerBalancesBefore = getBalances(client, seller.getAddress())
    sellerAlgosBefore = sellerBalancesBefore[0]
    print("Alice's balances:", sellerBalancesBefore)

    _, lastRoundTime = getLastBlockTimestamp(client)
    if lastRoundTime < startTime + 5:
        sleep(startTime + 5 - lastRoundTime)
    actualAppBalancesBefore = getBalances(client, get_application_address(appID))
    print("Sale escrow balances:", actualAppBalancesBefore, "\n")

    ##############################################################################################
    print("Carla is opting into NFT with ID", nftID)

    optInToAsset(client, nftID, bidder)    

    bidAmount = reserve
    bidderBalancesBefore = getBalances(client, bidder.getAddress())
    bidderAlgosBefore = bidderBalancesBefore[0]
    print("Carla wants to bid on NFT, her balances:", bidderBalancesBefore)
    print("Carla is placing bid for", bidAmount, "microAlgos")

    placeBid(client=client, appID=appID, bidder=bidder, bidAmount=bidAmount)
    print("Done\n")

    print("Math is opting into NFT with ID", nftID)

    optInToAsset(client, nftID, bidder2)    

    bidAmount = int(bidAmount*1.5)
    bidder2BalancesBefore = getBalances(client, bidder2.getAddress())
    bidder2AlgosBefore = bidder2BalancesBefore[0]
    print("Math wants to bid on NFT, his balances:", bidder2BalancesBefore)
    print("Math is placing bid for", bidAmount, "microAlgos")

    placeBid(client=client, appID=appID, bidder=bidder2, bidAmount=bidAmount)
    print("Done\n")

    print("sleep 3s")
    sleep(3)

    bidAmount = int(bidAmount*2)
    bidderBalancesBefore = getBalances(client, bidder.getAddress())
    bidderAlgosBefore = bidderBalancesBefore[0]
    print("Carla wants to bid on NFT, her balances:", bidderBalancesBefore)
    print("Carla is placing bid for", bidAmount, "microAlgos")

    placeBid(client=client, appID=appID, bidder=bidder, bidAmount=bidAmount)
    print("Done\n")

    print("Not waiting for the Sale to finish !! STILL ON GOING\n")
    
    sellerNftBalance = getBalances(client, seller.getAddress())
    creatorNftBalance = getBalances(client, creator.getAddress())
    bidderNftBalance = getBalances(client, bidder.getAddress())
    bidder2NftBalance = getBalances(client, bidder2.getAddress())
    print("The seller holds the following = ",sellerNftBalance)
    print("The creator holds the following = ",creatorNftBalance)
    print("The bidder1 holds the following = ",bidderNftBalance)
    print("The bidder2 holds the following = ",bidder2NftBalance)


    print("Alice is closing out the Sale to cancel all bids...\n")
    closeSale(client, appID, seller)

    actualAppBalances = getBalances(client, get_application_address(appID))
    expectedAppBalances = {0: 0}
    print("The Sale escrow now holds the following:", actualAppBalances)
    assert actualAppBalances == expectedAppBalances

    sellerNftBalance = getBalances(client, seller.getAddress())
    creatorNftBalance = getBalances(client, creator.getAddress())
    bidderNftBalance = getBalances(client, bidder.getAddress())
    bidder2NftBalance = getBalances(client, bidder2.getAddress())
    print("The seller holds now the following = ",sellerNftBalance)
    print("The creator holds now the following = ",creatorNftBalance)
    print("The bidder1 holds now the following = ",bidderNftBalance)
    print("The bidder2 holds now the following = ",bidder2NftBalance)


def test_close_no_bids():
    client = getAlgodClient()

    creator = getTemporaryAccount(client)
    seller = getTemporaryAccount(client)

    nftAmount = 1
    nftID = createDummyAsset(client, nftAmount, seller)

    startTime = int(time()) + 10  # start time is 10 seconds in the future
    endTime = startTime + 30  # end time is 30 seconds after start
    reserve = 100000  # 1 Algo
    increment = 10 # 0.1 Algo

    gems_fees_acc = getTemporaryAccount(client)
    royalties_fees_acc = getTemporaryAccount(client)
    gems_fees_percentage = 5
    royalties_fees_percentage = 10
    late_bidding_delay = 10 # seconds

    appID = createSaleApp(
        client=client,
        sender=creator,
        seller=seller.getAddress(),
        nftID=nftID,
        startTime=startTime,
        endTime=endTime,
        reserve=reserve,
        minBidIncrement=increment,
        gems_fees_wallet= gems_fees_acc.getAddress(),
        royalties_wallet= royalties_fees_acc.getAddress(),
        gems_fees_percent= gems_fees_percentage,
        royalties_fees_percent= royalties_fees_percentage,
        late_bidding_delay= late_bidding_delay
    )

    setupSaleApp(
        client=client,
        appID=appID,
        funder=creator,
        nftHolder=seller,
        nftID=nftID,
        nftAmount=nftAmount,
    )

    _, lastRoundTime = getLastBlockTimestamp(client)
    if lastRoundTime < endTime + 5:
        sleep(endTime + 5 - lastRoundTime)

    closeSale(client, appID, seller)

    actualAppBalances = getBalances(client, get_application_address(appID))
    expectedAppBalances = {0: 0}

    assert actualAppBalances == expectedAppBalances

    sellerNftBalance = getBalances(client, seller.getAddress())[nftID]
    assert sellerNftBalance == nftAmount


def test_close_reserve_not_met():
    client = getAlgodClient()

    creator = getTemporaryAccount(client)
    seller = getTemporaryAccount(client)

    nftAmount = 1
    nftID = createDummyAsset(client, nftAmount, seller)

    startTime = int(time()) + 10  # start time is 10 seconds in the future
    endTime = startTime + 30  # end time is 30 seconds after start
    reserve = 1_000_000  # 1 Algo
    increment = 10  # 0.1 Algo
    
    gems_fees_acc = getTemporaryAccount(client)
    royalties_fees_acc = getTemporaryAccount(client)
    gems_fees_percentage = 5
    royalties_fees_percentage = 10
    late_bidding_delay = 10 # seconds

    appID = createSaleApp(
        client=client,
        sender=creator,
        seller=seller.getAddress(),
        nftID=nftID,
        startTime=startTime,
        endTime=endTime,
        reserve=reserve,
        minBidIncrement=increment,
        gems_fees_wallet= gems_fees_acc.getAddress(),
        royalties_wallet= royalties_fees_acc.getAddress(),
        gems_fees_percent= gems_fees_percentage,
        royalties_fees_percent= royalties_fees_percentage,
        late_bidding_delay= late_bidding_delay
    )

    setupSaleApp(
        client=client,
        appID=appID,
        funder=creator,
        nftHolder=seller,
        nftID=nftID,
        nftAmount=nftAmount,
    )

    bidder = getTemporaryAccount(client)

    _, lastRoundTime = getLastBlockTimestamp(client)
    if lastRoundTime < startTime + 5:
        sleep(startTime + 5 - lastRoundTime)

    bidAmount = 500_000  # 0.5 Algos
    placeBid(client=client, appID=appID, bidder=bidder, bidAmount=bidAmount)

    bidderAlgosBefore = getBalances(client, bidder.getAddress())[0]

    _, lastRoundTime = getLastBlockTimestamp(client)
    if lastRoundTime < endTime + 5:
        sleep(endTime + 5 - lastRoundTime)

    closeSale(client, appID, seller)

    actualAppBalances = getBalances(client, get_application_address(appID))
    expectedAppBalances = {0: 0}

    assert actualAppBalances == expectedAppBalances

    bidderAlgosAfter = getBalances(client, bidder.getAddress())[0]

    # bidder should receive a refund of their bid, minus the txn fee
    assert bidderAlgosAfter - bidderAlgosBefore >= bidAmount - 1_000

    sellerNftBalance = getBalances(client, seller.getAddress())[nftID]
    assert sellerNftBalance == nftAmount


def test_close_reserve_met():
    client = getAlgodClient()

    creator = getTemporaryAccount(client)
    seller = getTemporaryAccount(client)

    nftAmount = 1
    nftID = createDummyAsset(client, nftAmount, seller)

    startTime = int(time()) + 10  # start time is 10 seconds in the future
    endTime = startTime + 30  # end time is 30 seconds after start
    reserve = 1_000_000  # 1 Algo
    increment = 10  # 0.1 Algo

    
    gems_fees_acc = getTemporaryAccount(client)
    royalties_fees_acc = getTemporaryAccount(client)
    gems_fees_percentage = 5
    royalties_fees_percentage = 10
    late_bidding_delay = 10 # seconds

    appID = createSaleApp(
        client=client,
        sender=creator,
        seller=seller.getAddress(),
        nftID=nftID,
        startTime=startTime,
        endTime=endTime,
        reserve=reserve,
        minBidIncrement=increment,
        gems_fees_wallet= gems_fees_acc.getAddress(),
        royalties_wallet= royalties_fees_acc.getAddress(),
        gems_fees_percent= gems_fees_percentage,
        royalties_fees_percent= royalties_fees_percentage,
        late_bidding_delay= late_bidding_delay
    )

    setupSaleApp(
        client=client,
        appID=appID,
        funder=creator,
        nftHolder=seller,
        nftID=nftID,
        nftAmount=nftAmount,
    )

    sellerAlgosBefore = getBalances(client, seller.getAddress())[0]

    bidder = getTemporaryAccount(client)

    _, lastRoundTime = getLastBlockTimestamp(client)
    if lastRoundTime < startTime + 5:
        sleep(startTime + 5 - lastRoundTime)

    bidAmount = reserve
    placeBid(client=client, appID=appID, bidder=bidder, bidAmount=bidAmount)

    optInToAsset(client, nftID, bidder)

    _, lastRoundTime = getLastBlockTimestamp(client)
    if lastRoundTime < endTime + 5:
        sleep(endTime + 5 - lastRoundTime)

    closeSale(client, appID, seller)

    actualAppBalances = getBalances(client, get_application_address(appID))
    expectedAppBalances = {0: 0}

    assert actualAppBalances == expectedAppBalances

    bidderNftBalance = getBalances(client, bidder.getAddress())[nftID]

    assert bidderNftBalance == nftAmount

    actualSellerBalances = getBalances(client, seller.getAddress())

    assert len(actualSellerBalances) == 2
    # seller should receive the bid amount, minus the txn fee
    assert actualSellerBalances[0] >= sellerAlgosBefore + bidAmount - 1_000
    assert actualSellerBalances[nftID] == 0
