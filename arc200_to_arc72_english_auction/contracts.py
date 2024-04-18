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
    def transferNFT(to_account: Expr) -> Expr:
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
        return Seq(
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields(
                {
                    TxnField.type_enum: TxnType.ApplicationCall,
                    TxnField.application_id: App.globalGet(arc200_app_id_key),
                    TxnField.applications: [App.globalGet(arc200_app_id_key)],
                    TxnField.accounts: [from_, to_],
                    TxnField.application_args: [
                        Bytes("base16", "f43a105d"),  # arc200_transferFrom
                        from_,  # FROM: approver/owner
                        to_,  # TO
                        Itob(amount_),  # ARC200 Amount
                    ],
                }
            ),
            InnerTxnBuilder.Submit(),
        )

    # READ ONLY ARC200 FUNCTIONS
    @Subroutine(TealType.uint64)
    def arc200_allowance_to_sale(owner_: Expr) -> Expr:
        return Seq(
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields(
                {
                    TxnField.type_enum: TxnType.ApplicationCall,
                    TxnField.application_id: App.globalGet(arc200_app_id_key),
                    TxnField.applications: [
                        App.globalGet(arc200_app_id_key),
                    ],
                    TxnField.accounts: [Global.current_application_address()],
                    TxnField.application_args: [
                        Bytes("base16", "bbb319f3"),  # arc200_allowance
                        owner_,  # arg: owner
                        Global.current_application_address(),  # arg: spender (current address)
                    ],
                }
            ),
            InnerTxnBuilder.Submit(),
            Return(
                Btoi(InnerTxn.last_log())
            ),  # last_log() is the last return value, as Bytes, convert to Int
        )

    @Subroutine(TealType.uint64)
    def arc200_balanceOf(owner_: Expr) -> Expr:
        return Seq(
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields(
                {
                    TxnField.type_enum: TxnType.ApplicationCall,
                    TxnField.application_id: App.globalGet(arc200_app_id_key),
                    TxnField.applications: [
                        App.globalGet(arc200_app_id_key),
                    ],
                    TxnField.accounts: [Global.current_application_address()],
                    TxnField.application_args: [
                        Bytes("base16", "82e573c4"),  # arc200_balanceOf
                        owner_,  # arg: owner
                    ],
                }
            ),
            InnerTxnBuilder.Submit(),
            Return(
                Btoi(InnerTxn.last_log())
            ),  # last_log() is the last return value, as Bytes, convert to Int
        )

    ### Optional OptIn if ARC200 is stateful app
    @Subroutine(TealType.none)
    def OptInARC200() -> Expr:
        return Seq(
            # Make sure this contract is Opted in to the ARC200 before trying to transferFrom
            # Opt-in to the payment token (ARC200) to be able to have a sale balance (if ARC200 is implemented like that?)
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields(
                {
                    TxnField.type_enum: TxnType.ApplicationCall,
                    TxnField.application_id: App.globalGet(arc200_app_id_key),
                    TxnField.applications: [App.globalGet(arc200_app_id_key)],
                    TxnField.accounts: [
                        Gtxn[1].accounts[0],
                        Gtxn[1].accounts[1],
                        Global.current_application_address(),
                    ],
                    TxnField.on_completion: OnComplete.OptIn,
                }
            ),
            InnerTxnBuilder.Submit(),
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
    allowed_ARC200_amount = arc200_allowance_to_sale(Txn.sender())
    actual_bidder_ARC200_balance = arc200_balanceOf(Txn.sender())
    on_bid = Seq(
        allowed_ARC200_amount,
        actual_bidder_ARC200_balance,
        Assert(
            # When bid is placed, check:
            # - if auction is still on-going
            # - if allowance by the Buyer is correct
            And(
                Global.latest_timestamp()
                < App.globalGet(end_time_key),  # auction is not ended
                allowed_ARC200_amount
                >= App.globalGet(reserve_amount_key),  # greater than reserve
                # Check if bid >= 10% above last bid
                allowed_ARC200_amount
                >= Div(Mul(App.globalGet(lead_bid_amount_key), Int(110)), Int(100)),
                # Check if bidder isn't lying on his balance
                actual_bidder_ARC200_balance >= allowed_ARC200_amount,
            )
        ),
        Seq(
            If(App.globalGet(lead_bid_account_key) != Global.zero_address()).Then(
                # it's an approval-based auction: we don't have to repay ARC200
                # but we can help "de-approve" for the last bidder by transfering to itself
                ARC200transferFrom(
                    lead_bid_account_key, lead_bid_account_key, lead_bid_amount_key
                )  # optional de-allowance
            ),
            # Update the new amount
            App.globalPut(lead_bid_amount_key, allowed_ARC200_amount),
            App.globalPut(lead_bid_account_key, Txn.sender()),
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
                            transferNFT(
                                App.globalGet(lead_bid_account_key),
                            ),
                            # Transfer lead-bidding-amount ARC200 Token from LEAD BIDDER to SELLER
                            ARC200transferFrom(
                                App.globalGet(lead_bid_account_key),
                                App.globalGet(seller_key),
                                App.globalGet(lead_bid_amount_key),
                            ),
                            # Reset the bidding-variables to avoid repeat attack
                            App.globalPut(lead_bid_amount_key, Int(0)),
                            App.globalPut(lead_bid_account_key, Global.zero_address()),
                            SendNoteToFees(Int(0), Bytes("auction,close_buy,200/72")),
                        )
                    )
                    .Else(
                        # CASE B:   The seller doesn't actually own the ARC72
                        #           Lead bidder keeps its ARC200 tokens, optional de-allowance below
                        ARC200transferFrom(
                            lead_bid_account_key,
                            lead_bid_account_key,
                            lead_bid_amount_key,
                        ),  # optional de-allowance
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
