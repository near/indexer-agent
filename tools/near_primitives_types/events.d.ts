export type Log = {
    log: String;
    relatedReceiptId: String;
};
/**
 * This structure is an ephemeral entity to provide access to the [Events Standard](https://github.com/near/NEPs/blob/master/neps/nep-0297.md) structure and keep data about the related `Receipt` for convenience.
 *
 * #### Interface for Capturing Data About an Event in `handleStreamerMessage()`
 *
 * The interface to capture data about an event has the following arguments:
 *  - `standard`: name of standard, e.g. nep171
 *  - `version`: e.g. 1.0.0
 *  - `event`: type of the event, e.g. `nft_mint`
 *  - `data`: associate event data. Strictly typed for each set {standard, version, event} inside corresponding NEP
 */
export declare class Event {
    readonly relatedReceiptId: string;
    readonly rawEvent: RawEvent;
    constructor(relatedReceiptId: string, rawEvent: RawEvent);
    static fromLog: (log: string) => Event;
}
/**
 * This structure is a copy of the [JSON Events](https://github.com/near/NEPs/blob/master/neps/nep-0297.md) structure representation.
 */
export declare class RawEvent {
    readonly event: string;
    readonly standard: string;
    readonly version: string;
    readonly data: JSON | undefined;
    constructor(event: string, standard: string, version: string, data: JSON | undefined);
    static isEvent: (log: string) => boolean;
    static fromLog: (log: string) => RawEvent;
}
export type Events = {
    events: Event[];
};
