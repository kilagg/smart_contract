from pyteal import *


def approval_program():
    # PARAMETERS
    seller_key = Bytes("seller")
    fees_address = Bytes("fees_address")

    nft_app_id_key = Bytes("nft_app_id")  # parameter for the ARC-72 asset
    arc200_app_id_key = Bytes("arc200_app_id")  # parameter for ARC-200 asset ID

    nft_id_key = Bytes("nft_id")
    end_time_key = Bytes("end")

    late_bid_delay_key = Bytes("late_bid_delay")
    lead_bid_account_key = Bytes("bid_account")
    reserve_amount_key = Bytes("reserve_amount")
    lead_bid_amount_key = Bytes("bid_amount")

    #################################### TRANSFER FUNCTIONS (external ontracts) #####################################
    #####################################   ARC72 FUNCTIONS  #####################################
    @Subroutine(TealType.none)
    def transferFromNFT(to_account: Expr) -> Expr:
        return Seq(
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields(
                {
                    TxnField.type_enum: TxnType.ApplicationCall,
                    TxnField.application_id: App.globalGet(nft_app_id_key),
                    TxnField.on_completion: OnComplete.NoOp,
                    TxnField.application_args: [
                        Bytes("base16", "f2f194a0"),
                        App.globalGet(seller_key),
                        to_account,
                        App.globalGet(nft_id_key),
                    ],
                }
            ),
            InnerTxnBuilder.Submit(),
        )

    @Subroutine(TealType.bytes)
    def arc72_owner() -> Expr:
        return Seq(
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields(
                {
                    TxnField.type_enum: TxnType.ApplicationCall,
                    TxnField.application_id: App.globalGet(nft_app_id_key),
                    TxnField.applications: [
                        App.globalGet(nft_app_id_key),
                    ],
                    TxnField.accounts: [Global.current_application_address()],
                    TxnField.application_args: [
                        Bytes("base16", "79096a14"),  # arc72_OwnerOf
                        App.globalGet(nft_id_key),  # arg: tokenId
                    ],
                }
            ),
            InnerTxnBuilder.Submit(),
            Return(InnerTxn.last_log()),
        )

    #####################################   ARC200 FUNCTIONS  #####################################
    @Subroutine(TealType.none)
    def ARC200transferFrom(from_: Expr, to_: Expr, amount_: Expr) -> Expr:
        zero_padding = BytesZero(Int(24))
        byte_slice_amount = Itob(amount_)
        full_32_byte_amount = Concat(byte_slice_amount, zero_padding)
        return Seq(
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields({
                TxnField.type_enum: TxnType.ApplicationCall,
                TxnField.application_id: App.globalGet(arc200_app_id_key),
                TxnField.applications: [App.globalGet(arc200_app_id_key)],
                TxnField.accounts: [from_, to_],
                TxnField.application_args: [
                    Bytes("base16", "da7025b9"),  # arc200_transfer
                    to_,  # TO
                    full_32_byte_amount,  # ARC200 Amount
                ],
            }),
            InnerTxnBuilder.Submit(),
        )

    @Subroutine(TealType.none)
    def ARC200transfer(to_: Expr, amount_: Expr) -> Expr:
        return Seq(
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields(
                {
                    TxnField.type_enum: TxnType.ApplicationCall,
                    TxnField.application_id: App.globalGet(arc200_app_id_key),
                    TxnField.applications: [App.globalGet(arc200_app_id_key)],
                    TxnField.accounts: [to_],
                    TxnField.application_args: [
                        Bytes("base16", "1df06e69"),  # arc200_transfer
                        to_,                          # TO
                        Itob(amount_),                # ARC200 Amount
                    ],
                }
            ),
            InnerTxnBuilder.Submit(),
        )

    @Subroutine(TealType.none)
    def repayPreviousLeadBidder(prevLeadBidder: Expr, prevLeadBidAmount: Expr) -> Expr:
        return Seq( # refund the last bidder from the contract ARC200 funds
            ARC200transfer(prevLeadBidder, prevLeadBidAmount)
        )
        
    ########################################################### LOGGING FOR INDEXER PURPOSES ######################################################
    @Subroutine(TealType.none)
    def SendNoteToFees(amount: Expr, note: Expr) -> Expr:
        return Seq(
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields(
                {
                    TxnField.type_enum: TxnType.Payment,
                    TxnField.amount: amount,
                    TxnField.sender: Global.current_application_address(),
                    TxnField.receiver: App.globalGet(fees_address),
                    TxnField.note: note,
                }
            ),
            InnerTxnBuilder.Submit(),
        )

    ################################################################    CLOSURE FUNCTIONS   ###########################################################
    @Subroutine(TealType.none)
    def closeAccountTo(account: Expr) -> Expr:
        return If(Balance(Global.current_application_address()) != Int(0)).Then(
            Seq(
                InnerTxnBuilder.Begin(),
                InnerTxnBuilder.SetFields(
                    {
                        TxnField.type_enum: TxnType.Payment,
                        TxnField.close_remainder_to: account,
                    }
                ),
                InnerTxnBuilder.Submit(),
            )
        )

    on_create = Seq(
        # Addresses
        App.globalPut(seller_key, Txn.application_args[0]),
        App.globalPut(nft_app_id_key, Btoi(Txn.application_args[1])),
        App.globalPut(arc200_app_id_key, Btoi(Txn.application_args[2])),
        App.globalPut(fees_address, Txn.application_args[3]),
        # core parameters
        App.globalPut(nft_id_key, Txn.application_args[4]),
        App.globalPut(reserve_amount_key, Btoi(Txn.application_args[5])),
        App.globalPut(end_time_key, Btoi(Txn.application_args[6])),
        # global variables
        App.globalPut(
            lead_bid_account_key, Global.zero_address()
        ),  # no bidder at creation
        App.globalPut(late_bid_delay_key, Int(600)),  # 10 minute to delay
        App.globalPut(
            lead_bid_amount_key, Int(0)
        ),  # 0 at initialisation, there is no bidder
        Approve(),
    )

    # Fetch Bidder ARC200 current balance and allowance towards this contract
    bid_amount = Btoi(Txn.application_args[1])
    on_bid = Seq(
        Assert(
            # When bid is placed, we check:
            # - if auction is still on-going
            # - if the bid amount is >= reserve and >= 10% above last bid
            # - then we immediately transfer the bid amount, ensuring that we have secured these funds
            And(
                Global.latest_timestamp()
                < App.globalGet(end_time_key),  # auction is not ended
                bid_amount >= App.globalGet(reserve_amount_key),  # greater than reserve
                bid_amount
                >= Div(Mul(App.globalGet(lead_bid_amount_key), Int(110)), Int(100)),
            )
        ),
        Seq(
            # First fetch bid_amount ARC200 of the current bid: from Bidder -> Current App
            ARC200transferFrom(
                Txn.sender(), 
                Global.current_application_address(), 
                bid_amount),
            # Then repay previous lead bidder, if it's not the first bid
            If(App.globalGet(lead_bid_account_key) != Global.zero_address()).Then(
                repayPreviousLeadBidder(
                    App.globalGet(lead_bid_account_key),
                    App.globalGet(lead_bid_amount_key),
                )
            ),
            # Update the new amount
            App.globalPut(lead_bid_account_key, Txn.sender()),
            App.globalPut(lead_bid_amount_key, bid_amount),
            # DELAY MECHANISM: extend end_time if last minute bid
            If(
                Global.latest_timestamp() + App.globalGet(late_bid_delay_key)
                >= App.globalGet(end_time_key)
            ).Then(
                App.globalPut(
                    end_time_key,
                    (Global.latest_timestamp() + App.globalGet(late_bid_delay_key)),
                )
            ),
            Approve(),
        ),
    )

    on_call_method = Txn.application_args[0]
    on_call = Cond(
        [on_call_method == Bytes("pre_validate"), Approve()],
        [on_call_method == Bytes("bid"), on_bid],
    )

    on_delete = Seq(
        # Case 1. No bids on contract, then refund all remaining VOI funds to Seller
        If(App.globalGet(lead_bid_account_key) == Global.zero_address())
        .Then(
            Seq(
                If(App.globalGet(end_time_key) > Global.latest_timestamp()).Then(
                    # Only sender/creator can close early, if on-going
                    Assert(
                        Or(
                            Txn.sender() == App.globalGet(seller_key),
                            Txn.sender() == Global.creator_address(),
                        )
                    ),
                ),
                SendNoteToFees(Int(0), Bytes("auction,close_none,200/72")),
                # Send all VOI funds to the seller
                closeAccountTo(App.globalGet(seller_key)),
                Approve(),
            )
        )
        .Else(
            # Case 2. There have been ARC200 bids AND the auction successfully ended
            If(App.globalGet(end_time_key) <= Global.latest_timestamp()).Then(
                Seq(
                    If(arc72_owner() == App.globalGet(seller_key))
                    .Then(
                        # CASE A: The seller has the ARC72, we proceed to swap
                        Seq(
                            # Transfer ARC72 NFT from SELLER to LEAD BIDDER
                            transferFromNFT(
                                App.globalGet(lead_bid_account_key),
                            ),
                            # Transfer lead-bidding-amount ARC200 Token from Current App to SELLER
                            ARC200transferFrom(
                                Global.current_application_address(),
                                App.globalGet(seller_key),
                                App.globalGet(lead_bid_amount_key),
                            ),
                            SendNoteToFees(Int(0), Bytes("auction,close_buy,200/72")),
                            # Reset the bidding-variables to avoid repeat attack: optional
                            App.globalPut(lead_bid_amount_key, Int(0)),
                            App.globalPut(lead_bid_account_key, Global.zero_address()),
                        )
                    )
                    .Else(
                        # CASE B:   The seller doesn't actually own the ARC72
                        #           Refund latest bidder
                        repayPreviousLeadBidder(
                            App.globalGet(lead_bid_account_key),
                            App.globalGet(lead_bid_amount_key),
                        ),
                        SendNoteToFees(Int(0), Bytes("auction,close_refund,200/72")),
                    ),
                    # send remaining VOI funds to the seller
                    closeAccountTo(App.globalGet(seller_key)),
                    Approve(),
                )
            ),
        ),
        # Else: auction is ongoing and has bids, we have to wait for it to end.
        Reject(),
    )

    program = Cond(
        [Txn.application_id() == Int(0), on_create],
        [Txn.on_completion() == OnComplete.NoOp, on_call],
        [Txn.on_completion() == OnComplete.DeleteApplication, on_delete],
        [
            Or(
                Txn.on_completion() == OnComplete.OptIn,
                Txn.on_completion() == OnComplete.CloseOut,
                Txn.on_completion() == OnComplete.UpdateApplication,
            ),
            Reject(),
        ],
    )

    return program
