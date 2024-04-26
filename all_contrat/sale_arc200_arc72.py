from pyteal import *


def approval_program():
    # PARAMETERS
    seller_key = Bytes("seller")
    nft_id_key = Bytes("nft_id")
    nft_app_id_key = Bytes("nft_app_id")
    arc200_app_id_key = Bytes("arc200_app_id")
    nft_price = Bytes("price")
    fees_address = Bytes("fees_address")
    nft_app_address = Bytes("nft_app_address")

    @Subroutine(TealType.none)
    def ARC72transferFrom(to_account: Expr) -> Expr:
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
    def ARC200fund() -> Expr:
        return Seq(
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields(
                {
                    TxnField.type_enum: TxnType.Payment,
                    TxnField.amount: Int(28500),
                    TxnField.sender: Global.current_application_address(),
                    TxnField.receiver: App.globalGet(nft_app_address)
                }
            ),
            InnerTxnBuilder.Submit(),
        )

    @Subroutine(TealType.none)
    def ARC200transferFrom() -> Expr:
        return Seq(
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields(
                {
                    TxnField.type_enum: TxnType.ApplicationCall,
                    TxnField.application_id: App.globalGet(arc200_app_id_key),
                    TxnField.on_completion: OnComplete.NoOp,
                    TxnField.application_args: [
                        Bytes("base16", "da7025b9"),
                        App.globalGet(seller_key),
                        App.globalGet(nft_price)
                    ]
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
    def closeAccountTo() -> Expr:
        return If(Balance(Global.current_application_address()) != Int(0)).Then(
            Seq(
                InnerTxnBuilder.Begin(),
                InnerTxnBuilder.SetFields(
                    {
                        TxnField.type_enum: TxnType.Payment,
                        TxnField.close_remainder_to: App.globalGet(seller_key),
                    }
                ),
                InnerTxnBuilder.Submit(),
            )
        )

    on_create = Seq(
        App.globalPut(seller_key, Txn.application_args[0]),
        App.globalPut(nft_app_id_key, Btoi(Txn.application_args[1])),
        App.globalPut(nft_id_key, Txn.application_args[2]),
        App.globalPut(arc200_app_id_key, Btoi(Txn.application_args[3])),
        App.globalPut(nft_price, Txn.application_args[4]),
        App.globalPut(fees_address, Txn.application_args[5]),
        App.globalPut(nft_app_address, Txn.application_args[6]),
        Approve(),
    )

    on_buy = Seq(
        Seq(
            ARC200fund(),
            ARC200transferFrom(),
            ARC72transferFrom(Txn.sender()),
            SendNoteToFees(Int(0), Bytes("sale,buy,200/72")),
        ),
        Approve()
    )

    new_price = Btoi(Txn.application_args[1])
    on_update_price = Seq(
        Assert(
            And(
                new_price > Int(0),
                Txn.sender() == Global.creator_address(),
            )
        ),
        SendNoteToFees(Int(0), Bytes("sale,update,200/72")),
        App.globalPut(nft_price, new_price),
        Approve(),
    )

    on_call_method = Txn.application_args[0]
    on_call = Cond(
        [on_call_method == Bytes("pre_validate"), Approve()],
        [on_call_method == Bytes("buy"), on_buy],
        [on_call_method == Bytes("update_price"), on_update_price],
    )

    on_delete = Seq(
        Assert(Txn.sender() == App.globalGet(seller_key)),
        SendNoteToFees(Int(0), Bytes("sale,close,200/72")),
        closeAccountTo(),
        Approve(),
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


if __name__ == "__main__":
    with open("approval.teal", "w") as f:
        compiled = compileTeal(approval_program(), mode=Mode.Application, version=10)
        from algosdk.v2client.algod import AlgodClient

        algod_token_tx = ""
        headers_tx = {"X-Algo-API-Token": algod_token_tx}
        client = AlgodClient(
            algod_token=algod_token_tx,
            algod_address="https://testnet-api.voi.nodly.io:443",
            headers=headers_tx,
        )
        print(client.compile(compiled)['result'])
        f.write(compiled)
