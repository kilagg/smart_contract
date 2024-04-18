from pyteal import *


def approval_program():
    # PARAMETERS
    seller_key = Bytes("seller")
    nft_id_key = Bytes("nft_id")
    nft_app_id_key = Bytes("nft_app_id")
    fees_address = Bytes("fees_address")
    end_time_key = Bytes("end")
    late_bid_delay_key = Bytes("late_bid_delay")
    lead_bid_account_key = Bytes("bid_account")
    reserve_amount_key = Bytes("reserve_amount")
    lead_bid_amount_key = Bytes("bid_amount")

    @Subroutine(TealType.none)
    def transferNFT(to_account: Expr) -> Expr:
        return Seq(
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields({
                TxnField.type_enum: TxnType.ApplicationCall,
                TxnField.application_id: App.globalGet(nft_app_id_key),
                TxnField.on_completion: OnComplete.NoOp,
                TxnField.application_args: [
                    Bytes("base16", "f2f194a0"),
                    App.globalGet(seller_key),
                    to_account,
                    App.globalGet(nft_id_key)
                ],
            }),
            InnerTxnBuilder.Submit(),
        )

    @Subroutine(TealType.none)
    def SendAlgoToSeller(amount: Expr) -> Expr:
        return Seq(
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields(
                {
                    TxnField.type_enum: TxnType.Payment,
                    TxnField.amount: amount,
                    TxnField.sender: Global.current_application_address(),
                    TxnField.receiver: App.globalGet(seller_key),
                }
            ),
            InnerTxnBuilder.Submit(),
        )

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

    @Subroutine(TealType.none)
    def repayPreviousLeadBidder(prevLeadBidder: Expr, prevLeadBidAmount: Expr) -> Expr:
        return Seq(
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields(
                {
                    TxnField.type_enum: TxnType.Payment,
                    TxnField.amount: prevLeadBidAmount - Global.min_txn_fee(),
                    TxnField.receiver: prevLeadBidder,
                }
            ),
            InnerTxnBuilder.Submit(),
        )

    on_create = Seq(
        App.globalPut(seller_key, Txn.application_args[0]),
        App.globalPut(nft_app_id_key, Btoi(Txn.application_args[1])),
        App.globalPut(nft_id_key, Txn.application_args[2]),
        App.globalPut(reserve_amount_key, Btoi(Txn.application_args[3])),
        App.globalPut(fees_address, Txn.application_args[4]),
        App.globalPut(end_time_key, Btoi(Txn.application_args[5])),
        App.globalPut(lead_bid_account_key, Global.zero_address()),  # no bidder at creation
        App.globalPut(late_bid_delay_key, Btoi(Int(600))),  # 10 minute to delay
        App.globalPut(lead_bid_amount_key, Btoi(Int(0))),  # 0 at initialisation, there is no bidder
        Approve(),
    )

    on_bid_txn_index = Txn.group_index() - Int(1)
    on_bid = Seq(
        Assert(
            And(
                Global.latest_timestamp() < App.globalGet(end_time_key),  # auction is not ended
                Gtxn[on_bid_txn_index].type_enum() == TxnType.Payment,
                Gtxn[on_bid_txn_index].receiver() == Global.current_application_address(),  # send to the contract
                Gtxn[on_bid_txn_index].amount() >= App.globalGet(reserve_amount_key),  # greater than reserve
                Gtxn[on_bid_txn_index].amount() >= Div(Mul(App.globalGet(lead_bid_amount_key), Int(110)), Int(100))
            )
        ),
        Seq(
            If(
                App.globalGet(lead_bid_account_key) != Global.zero_address()
            ).Then(
                repayPreviousLeadBidder(
                    App.globalGet(lead_bid_account_key),
                    App.globalGet(lead_bid_amount_key),
                )
            ),
            App.globalPut(lead_bid_amount_key, Gtxn[on_bid_txn_index].amount()),
            App.globalPut(lead_bid_account_key, Gtxn[on_bid_txn_index].sender()),
            SendNoteToFees(Int(0), Bytes("auction,bid,1/72")),
            If(
                Global.latest_timestamp() + App.globalGet(late_bid_delay_key) >= App.globalGet(end_time_key)
            ).Then(
                App.globalPut(end_time_key, (Global.latest_timestamp() + App.globalGet(late_bid_delay_key)))
            ),
            Approve(),
        )
    )

    on_call_method = Txn.application_args[0]
    on_call = Cond(
        [on_call_method == Bytes("bid"), on_bid],
    )

    on_delete = Seq(
        If(
            App.globalGet(end_time_key) <= Global.latest_timestamp()
        ).Then(
            Seq(
                If(
                    App.globalGet(lead_bid_account_key) != Global.zero_address()
                ).Then(
                    Seq(
                        SendNoteToFees(Int(0), Bytes("auction,close_buy,1/72")),
                        transferNFT(App.globalGet(lead_bid_account_key))
                    )
                )
                .Else(
                    SendNoteToFees(Int(0), Bytes("auction,close_none,1/72"))
                ),
                closeAccountTo(App.globalGet(seller_key)),
                Approve(),
            )
        ).Else(
            Seq(
                Assert(
                    Or(
                        # sender must either be the seller or the auction creator
                        Txn.sender() == App.globalGet(seller_key),
                        Txn.sender() == Global.creator_address(),
                    )
                ),
                # the auction is ongoing but seller wants to cancel
                If(
                    App.globalGet(lead_bid_account_key) != Global.zero_address()
                ).Then(
                    Seq(
                        # repay the lead bidder
                        SendNoteToFees(Int(0), Bytes("auction,close_none,1/72")),
                        repayPreviousLeadBidder(App.globalGet(lead_bid_account_key), App.globalGet(lead_bid_amount_key))
                    )
                )
                .Else(
                    SendNoteToFees(Int(0), Bytes("auction,close_none,1/72"))
                ),
                # send remaining funds to the seller
                closeAccountTo(App.globalGet(seller_key)),
                Approve(),
            )
        ),
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
