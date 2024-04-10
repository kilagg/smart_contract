from pyteal import *

def approval_program():
    # PARAMETERS
    owner_key = Bytes("owner")
    total_supply_key = Bytes("total_supply")
    decimals_key = Bytes("decimals")
    name_key = Bytes("name")
    symbol_key = Bytes("symbol")
    _init =  Bytes("_init")

    # ARC-200 methods
    # arc200_name implementation
    @Subroutine(TealType.bytes)
    def name() -> Expr:
        return App.globalGet(name_key)

    # arc200_symbol implementation
    @Subroutine(TealType.bytes)
    def symbol() -> Expr:
        return App.globalGet(symbol_key)

    # arc200_decimals implementation
    @Subroutine(TealType.uint64)
    def decimals() -> Expr:
        return App.globalGet(decimals_key)

    # arc200_totalSupply implementation
    @Subroutine(TealType.uint64)
    def totalSupply() -> Expr:
        return App.globalGet(total_supply_key)

    # arc200_balanceOf implementation
    @Subroutine(TealType.uint64)
    def balanceOf(account: Expr) -> Expr:
        return App.localGet(account, Bytes("balance"))

    # arc200_transfer implementation
    @Subroutine(TealType.none)
    def transfer(to: Expr, value: Expr) -> Expr:
        return Seq([
            Assert(App.localGet(Txn.sender(), Bytes("balance")) >= value),
            App.localPut(Txn.sender(), Bytes("balance"), App.localGet(Txn.sender(), Bytes("balance")) - value),
            App.localPut(to, Bytes("balance"), App.localGet(to, Bytes("balance")) + value),
            Log(Concat(Bytes("arc200_Transfer("), Txn.sender(), Bytes(","), to, Bytes(","), Itob(value), Bytes(")"))),
        ])

    @Subroutine(TealType.none)
    def transferFrom(from_addr: Expr, to: Expr, value: Expr) -> Expr:
        # Construct a unique key for the allowance
        allowance_key = Concat(from_addr, Txn.sender())
        # Retrieve the current allowance
        current_allowance = App.localGet(from_addr, allowance_key)
        # Calculate the new allowance
        new_allowance = current_allowance - value
        
        return Seq([
            Assert(App.localGet(from_addr, Bytes("balance")) >= value),  # Ensure sufficient balance
            Assert(current_allowance >= value),  # Ensure sufficient allowance
            App.localPut(from_addr, Bytes("balance"), App.localGet(from_addr, Bytes("balance")) - value),  # Deduct from the sender
            App.localPut(to, Bytes("balance"), App.localGet(to, Bytes("balance")) + value),  # Credit to the receiver
            App.localPut(from_addr, allowance_key, new_allowance),  # Update the allowance in the sender's state
            Log(Concat(Bytes("arc200_Transfer("), from_addr, Bytes(","), to, Bytes(","), Itob(value), Bytes(")"))),
        ])

    # arc200_approve implementation
    @Subroutine(TealType.none)
    def approve(spender: Expr, value: Expr) -> Expr:
        # Create a unique key for the allowance using both the owner's and spender's addresses
        allowance_key = Concat(Txn.sender(), spender)
        
        return Seq([
            App.localPut(Txn.sender(), allowance_key, value),  # Use the unique key for storing the allowance
            Log(Concat(Bytes("arc200_Approval("), Txn.sender(), Bytes(","), spender, Bytes(","), Itob(value), Bytes(")"))),
        ])

    # arc200_allowance implementation
    @Subroutine(TealType.uint64)
    def allowance(owner: Expr, spender: Expr) -> Expr:
        # Create a unique key for the allowance using both the owner's and spender's addresses
        allowance_key = Concat(owner, spender)
        
        return App.localGet(owner, allowance_key)  # Use the unique key to query the allowance


    # On creation, set the token parameters and the initial supply
    on_creation = Seq([
        App.globalPut(owner_key, Txn.sender()),
        App.globalPut(total_supply_key, Btoi(Txn.application_args[0])),
        App.globalPut(decimals_key, Btoi(Txn.application_args[1])),
        App.globalPut(name_key, Txn.application_args[2]),
        App.globalPut(symbol_key, Txn.application_args[3]),
        Approve()
    ])

    on_setup = Seq([    
        Assert(
            And(
                Txn.sender() == App.globalGet(owner_key),
                Int(0) == App.globalGet(_init) # forces 1 setup only
            )
        ),
        App.localPut(Txn.sender(), Bytes("balance"), App.globalGet(total_supply_key)),
        App.globalPut(_init, Int(1)),
        Approve(),
    ])
    
    on_call_method = Txn.application_args[0]
    on_call = Cond(
        [on_call_method == Bytes("setup"), on_setup],
        # Handle operations that don't return uint64 directly but require action, e.g., transfers
        [
            Or(
                on_call_method == Bytes("arc200_transfer"),
                on_call_method == Bytes("arc200_transferFrom"),
                on_call_method == Bytes("arc200_approve"),
            ),
            Cond(
                [on_call_method == Bytes("setup"), on_setup],
                [on_call_method == Bytes("arc200_transfer"), Seq([
                    transfer(Txn.application_args[1], Btoi(Txn.application_args[2])),
                    Approve(),
                ])],
                [on_call_method == Bytes("arc200_transferFrom"), Seq([
                    transferFrom(Txn.application_args[1], Txn.application_args[2], Btoi(Txn.application_args[3])),
                    Approve(),
                ])],
                [on_call_method == Bytes("arc200_approve"), Seq([
                    approve(Txn.application_args[1], Btoi(Txn.application_args[2])),
                    Approve(),
                ])]
            )
        ],
        # Separate branch for getter functions returning uint64 values
        [
            Or(
                on_call_method == Bytes("arc200_decimals"),
                on_call_method == Bytes("arc200_totalSupply"),
                on_call_method == Bytes("arc200_balanceOf"),
                on_call_method == Bytes("arc200_allowance"),
            ),
            Cond(
                [on_call_method == Bytes("arc200_decimals"), Return(decimals())],
                [on_call_method == Bytes("arc200_totalSupply"), Return(totalSupply())],
                [on_call_method == Bytes("arc200_balanceOf"), Return(balanceOf(Txn.application_args[1]))],
                [on_call_method == Bytes("arc200_allowance"), Return(allowance(Txn.application_args[1], Txn.application_args[2]))],
            )
        ],
        # Fallback for unrecognized methods
        [Int(1), Reject()]
    )

    # Program start
    program = Cond(
        [Txn.application_id() == Int(0), on_creation],
        [Txn.on_completion() == OnComplete.NoOp, on_call],
        [Txn.on_completion() == OnComplete.OptIn, Approve()]
    )

    return program

def clear_state_program():
    return Approve()

if __name__ == "__main__":
    with open("arc200_approval.teal", "w") as f:
        compiled = compileTeal(approval_program(), mode=Mode.Application, version=9)
        f.write(compiled)

    with open("arc200_clear_state.teal", "w") as f:
        compiled = compileTeal(clear_state_program(), mode=Mode.Application, version=9)
        f.write(compiled)
