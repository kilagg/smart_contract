from pyteal import *

FIXED_FEE = 0

def approval_program():
    # PARAMETERS
    seller_key = Bytes("seller")
    nft_id_key = Bytes("nft_id")
    nft_app_id_key = Bytes("nft_app_id")
    nft_max_price = Bytes("max_price")
    nft_min_price = Bytes("min_price")
    fees_address = Bytes("fees_address")
    start_time_key = Bytes("start")
    end_time_key = Bytes("end")

    @Subroutine(TealType.uint64)
    def is_valid_bid_amount(input_amount: Expr) -> Expr:
        return (
            # Full formula: max - (current-start)((max-min)/(end-start))
            input_amount >= Minus(
                    ## Max price
                    App.globalGet(nft_max_price),
                    ## Minus (current-start)((max-min)/(end-start))
                    Mul(
                        # elapsed time = current time - start time (>0)
                        Minus(
                            Global.latest_timestamp(),
                            App.globalGet(start_time_key) # this implicitly checks that now > start_time
                        ),
                        # * the decrement per second (ratio)
                        Div(
                            Minus(
                                App.globalGet(nft_max_price),
                                App.globalGet(nft_min_price)
                            ),
                            Minus(
                                # end - start
                                App.globalGet(end_time_key),
                                App.globalGet(start_time_key)
                            )
                        )
                    )
                )
        )

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
                    App.globalGet(seller_key),          # FROM: Seller
                    to_account,                         # To: top bidder()
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

    on_create = Seq(
        App.globalPut(seller_key, Txn.application_args[0]),
        App.globalPut(nft_app_id_key, Btoi(Txn.application_args[1])),
        App.globalPut(nft_id_key, Txn.application_args[2]),
        App.globalPut(nft_max_price, Btoi(Txn.application_args[3])),
        App.globalPut(nft_min_price, Btoi(Txn.application_args[4])),
        App.globalPut(fees_address, Txn.application_args[5]),
        App.globalPut(start_time_key, Btoi(Txn.application_args[6])),
        App.globalPut(end_time_key, Btoi(Txn.application_args[7])),
        # Check that max price > min price
        Assert(App.globalGet(nft_max_price) >= App.globalGet(nft_min_price)),
        # Check that start_time > end_time
        Assert(end_time_key > start_time_key),
        Approve(),
    )


    on_buy_txn_index = Txn.group_index() - Int(1)
    on_buy = Seq(
        Assert(
            And(
                is_valid_bid_amount(Gtxn[on_buy_txn_index].amount()),
                Gtxn[on_buy_txn_index].receiver() == Global.current_application_address(),
                Gtxn[on_buy_txn_index].type_enum() == TxnType.Payment,
                Gtxn[on_buy_txn_index].sender() == Txn.sender()
            )
        ),
        Seq(
            SendNoteToFees(Int(FIXED_FEE), Bytes("dutch,buy,1/72")),
            SendAlgoToSeller(Gtxn[on_buy_txn_index].amount()-Int(0)),  # pay seller immediately
            transferNFT(Gtxn[on_buy_txn_index].sender()), # send the NFT to the buyer
            Approve()
        ),
        Reject(),
    )

    on_call_method = Txn.application_args[0]
    on_call = Cond(
        [on_call_method == Bytes("pre_validate"), Approve()],
        [on_call_method == Bytes("buy"), on_buy]
    )

    on_delete = Seq(
        Assert(
            Or(
                Txn.sender() == App.globalGet(seller_key),
                Txn.sender() == Global.creator_address()
            )
        ),
        SendNoteToFees(Int(FIXED_FEE), Bytes("dutch,close,1/72")),
        closeAccountTo(App.globalGet(seller_key)),
        Approve(),
    )

    program = Cond(
        [Txn.application_id() == Int(0), on_create],
        [Txn.on_completion() == OnComplete.NoOp, on_call],
        [
            Txn.on_completion() == OnComplete.DeleteApplication,
            on_delete,
        ],
        [
            Or(
                Txn.on_completion() == OnComplete.OptIn,
                Txn.on_completion() == OnComplete.CloseOut
            ),
            Reject(),
        ],
    )

    return program


if __name__ == "__main__":

    with open("algo_arc72_dutch_approval.teal", "w") as f:
        compiled = compileTeal(approval_program(), mode=Mode.Application, version=10)
        f.write(compiled)
