from pyteal import *


def approval_program():
    # PARAMETERS
    seller_key = Bytes("seller")
    nft_id_key = Bytes("nft_id")
    nft_app_id_key = Bytes("nft_app_id")
    nft_price = Bytes("price")
    start_time_key = Bytes("start")

    @Subroutine(TealType.none)
    def transferNFT(to_account: Expr) -> Expr:
        return Seq(
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields({
                TxnField.type_enum: TxnType.ApplicationCall,
                TxnField.application_id: App.globalGet(nft_app_id_key),
                TxnField.on_completion: OnComplete.NoOp,
                TxnField.application_args: [
                    Bytes("arc72_transferFrom"),
                    Global.current_application_address(),
                    to_account,  # Assuming to_account is already a byte array
                    Itob(App.globalGet(nft_id_key))  # Assuming this returns a byte array or is converted appropriately
                ],
            }),
            InnerTxnBuilder.Submit(),
        )

    ##############################################################################################
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

    ################################################################################################################################################

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

    ################################################################################################################################################
    # VARIABLE SETUP
    on_create_start_time = Btoi(Txn.application_args[3])
    on_create = Seq(
        App.globalPut(seller_key, Txn.application_args[0]),
        App.globalPut(nft_app_id_key, Btoi(Txn.application_args[1])),
        App.globalPut(nft_id_key, Btoi(Txn.application_args[2])),
        App.globalPut(start_time_key, on_create_start_time),
        App.globalPut(nft_price, Btoi(Txn.application_args[4])),
        Assert(
            Global.latest_timestamp() < on_create_start_time
        ),
        Approve(),
    )

    ##############################################################################################################################
    on_buy_txn_index = Txn.group_index() - Int(1)
    # on_buy_nft_holding = AssetHolding.balance(
    #     Global.current_application_address(), App.globalGet(nft_id_key)
    # )
    on_buy = Seq(
        # on_buy_nft_holding,
        Assert(
            And(
                # the Sale has been set up
                # on_buy_nft_holding.hasValue(),
                # on_buy_nft_holding.value() > Int(0),
                Gtxn[on_buy_txn_index].amount() == App.globalGet(nft_price),
                # sender must send exact multiple of price to buy
                # the Sale has started
                App.globalGet(start_time_key) <= Global.latest_timestamp(),
                # the actual bid payment is before the app call
                Gtxn[on_buy_txn_index].type_enum() == TxnType.Payment,
                Gtxn[on_buy_txn_index].sender() == Txn.sender(),
                Gtxn[on_buy_txn_index].receiver() == Global.current_application_address(),
                Gtxn[on_buy_txn_index].amount() >= Global.min_txn_fee(),
            )
        ),
        Seq(
            SendAlgoToSeller(Gtxn[on_buy_txn_index].amount()),  # pay seller immediately
            transferNFT(
                Gtxn[on_buy_txn_index].sender()  # send the NFT to the seller.
            ),
            Approve()
        ),
        Reject(),
    )

    ################################################################################################################################################
    new_price = Btoi(Txn.application_args[1])
    on_update_price = Seq(
        Assert(
            Or(
                # sender must either be the seller or the Sale creator
                Txn.sender() == App.globalGet(seller_key),
                Txn.sender() == Global.creator_address()
            )
        ),
        Assert(new_price > Int(0)),
        ## UPDATE NEW PRICE
        App.globalPut(nft_price, new_price),
        Approve()
    )

    #######################
    ################################################################################################################################################
    #######################

    on_call_method = Txn.application_args[0]
    on_call = Cond(
        [on_call_method == Bytes("buy"), on_buy],
        [on_call_method == Bytes("update_price"), on_update_price]
    )

    ################################################################################################################################################

    on_delete = Seq(
        Assert(
            Or(
                # sender must either be the seller or the Sale creator
                Txn.sender() == App.globalGet(seller_key),
                Txn.sender() == Global.creator_address()
            )
        ),
        # the Sale is ongoing but seller wants to cancel
        transferNFT(
            App.globalGet(seller_key)
        ),
        # send remaining funds to the seller
        closeAccountTo(App.globalGet(seller_key)),
        Approve(),
    )

    #######################
    ################################################################################################################################################
    #######################

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
                Txn.on_completion() == OnComplete.CloseOut,
                Txn.on_completion() == OnComplete.UpdateApplication,
            ),
            Reject(),
        ],
    )

    return program


def clear_state_program():
    return Approve()


if __name__ == "__main__":
    with open("approval.teal", "w") as f:
        compiled = compileTeal(approval_program(), mode=Mode.Application, version=9)
        f.write(compiled)

    with open("clear_state.teal", "w") as f:
        compiled = compileTeal(clear_state_program(), mode=Mode.Application, version=9)
        f.write(compiled)
