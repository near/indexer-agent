import { ExecutionOutcomeWithReceipt, ExecutionStatus, ReceiptView } from './core/types';
import { Events, Event } from './events';
/**
 * This field is a simplified representation of the `ReceiptView` structure from [near-primitives](https://github.com/near/nearcore/tree/master/core/primitives).
 */
export declare class Receipt implements Events {
    /**
     * Defined the type of the `Receipt`: `Action` or `Data` representing the `ActionReceipt` and `DataReceipt`.
     */
    readonly receiptKind: ReceiptKind;
    /**
     * The ID of the `Receipt` of the `CryptoHash` type.
     */
    readonly receiptId: string;
    /**
     * The receiver account id of the `Receipt`.
     */
    readonly receiverId: string;
    /**
     * The predecessor account id of the `Receipt`.
     */
    readonly predecessorId: string;
    /**
     * Represents the status of `ExecutionOutcome` of the `Receipt`.
     */
    readonly status: ExecutionStatus;
    /**
     * The id of the `ExecutionOutcome` for the `Receipt`. Returns `null` if the `Receipt` isn’t executed yet and has a postponed status.
     */
    readonly executionOutcomeId?: string | undefined;
    /**
     * The original logs of the corresponding `ExecutionOutcome` of the `Receipt`.
     *
     * **Note:** not all of the logs might be parsed as JSON Events (`Events`).
     */
    readonly logs: string[];
    constructor(
    /**
     * Defined the type of the `Receipt`: `Action` or `Data` representing the `ActionReceipt` and `DataReceipt`.
     */
    receiptKind: ReceiptKind, 
    /**
     * The ID of the `Receipt` of the `CryptoHash` type.
     */
    receiptId: string, 
    /**
     * The receiver account id of the `Receipt`.
     */
    receiverId: string, 
    /**
     * The predecessor account id of the `Receipt`.
     */
    predecessorId: string, 
    /**
     * Represents the status of `ExecutionOutcome` of the `Receipt`.
     */
    status: ExecutionStatus, 
    /**
     * The id of the `ExecutionOutcome` for the `Receipt`. Returns `null` if the `Receipt` isn’t executed yet and has a postponed status.
     */
    executionOutcomeId?: string | undefined, 
    /**
     * The original logs of the corresponding `ExecutionOutcome` of the `Receipt`.
     *
     * **Note:** not all of the logs might be parsed as JSON Events (`Events`).
     */
    logs?: string[]);
    /**
     * Returns an Array of `Events` for the `Receipt`, if any. This might be empty if the `logs` field is empty or doesn’t contain JSON Events compatible log records.
     */
    get events(): Event[];
    static fromOutcomeWithReceipt: (outcomeWithReceipt: ExecutionOutcomeWithReceipt) => Receipt;
}
/**
 * `ReceiptKind` a simple `enum` to represent the `Receipt` type: either `Action` or `Data`.
 */
export declare enum ReceiptKind {
    Action = "Action",
    Data = "Data"
}
/**
 * `Action` is the structure with the fields and data relevant to an `ActionReceipt`.
 *
 * Basically, `Action` is the structure that indexer developers will be encouraged to work the most in their action-oriented indexers.
 */
export declare class Action {
    /**
     * The id of the corresponding `Receipt`
     */
    readonly receiptId: string;
    /**
     * The predecessor account id of the corresponding `Receipt`.
     * This field is a piece of denormalization of the structures (`Receipt` and `Action`).
     */
    readonly predecessorId: string;
    /**
     * The receiver account id of the corresponding `Receipt`.
     * This field is a piece of denormalization of the structures (`Receipt` and `Action`).
     */
    readonly receiverId: string;
    /**
     * The signer account id of the corresponding `Receipt`
     */
    readonly signerId: string;
    /**
     * The signer’s PublicKey for the corresponding `Receipt`
     */
    readonly signerPublicKey: string;
    /**
     * An array of `Operation` for this `ActionReceipt`
     */
    readonly operations: Operation[];
    constructor(
    /**
     * The id of the corresponding `Receipt`
     */
    receiptId: string, 
    /**
     * The predecessor account id of the corresponding `Receipt`.
     * This field is a piece of denormalization of the structures (`Receipt` and `Action`).
     */
    predecessorId: string, 
    /**
     * The receiver account id of the corresponding `Receipt`.
     * This field is a piece of denormalization of the structures (`Receipt` and `Action`).
     */
    receiverId: string, 
    /**
     * The signer account id of the corresponding `Receipt`
     */
    signerId: string, 
    /**
     * The signer’s PublicKey for the corresponding `Receipt`
     */
    signerPublicKey: string, 
    /**
     * An array of `Operation` for this `ActionReceipt`
     */
    operations: Operation[]);
    static isActionReceipt: (receipt: ReceiptView) => boolean;
    static fromReceiptView: (receipt: ReceiptView) => Action | null;
}
declare class DeployContract {
    readonly code: Uint8Array;
    constructor(code: Uint8Array);
}
declare class FunctionCall {
    readonly methodName: string;
    readonly args: Uint8Array;
    readonly gas: number;
    readonly deposit: string;
    constructor(methodName: string, args: Uint8Array, gas: number, deposit: string);
}
declare class Transfer {
    readonly deposit: string;
    constructor(deposit: string);
}
declare class Stake {
    readonly stake: number;
    readonly publicKey: string;
    constructor(stake: number, publicKey: string);
}
declare class AddKey {
    readonly publicKey: string;
    readonly accessKey: AccessKey;
    constructor(publicKey: string, accessKey: AccessKey);
}
declare class DeleteKey {
    readonly publicKey: string;
    constructor(publicKey: string);
}
declare class DeleteAccount {
    readonly beneficiaryId: string;
    constructor(beneficiaryId: string);
}
/**
 * A representation of the original `ActionView` from [near-primitives](https://github.com/near/nearcore/tree/master/core/primitives).
 */
export type Operation = 'CreateAccount' | DeployContract | FunctionCall | Transfer | Stake | AddKey | DeleteKey | DeleteAccount;
export declare class AccessKey {
    readonly nonce: number;
    readonly permission: string | AccessKeyFunctionCallPermission;
    constructor(nonce: number, permission: string | AccessKeyFunctionCallPermission);
}
declare class AccessKeyFunctionCallPermission {
    readonly allowance: string;
    readonly receiverId: string;
    readonly methodNames: string[];
    constructor(allowance: string, receiverId: string, methodNames: string[]);
}
export {};
