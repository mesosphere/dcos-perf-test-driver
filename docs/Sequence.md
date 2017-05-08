
# Sequence

- Start a test session
- Load all policies in the session
- Start every policy -> This will enter the `Start` FSM state
- Each policy should switch to `Ready` state when ready
- Dispatch the `onStart` event to every policy
- Dispatch the `onTick` event every second
- Take property snapshot after every event in the bus
- If a property has changed, update linked channels
- Run the policy FSMs until they all switch to `End` state

## SingleDeployment policy

- While in `Start` state
    - It switches to `Ready` state
- While in `Ready` state
    - When it receives `onStart` event it sets the defined properties
    - It switches to `Wait` state
- While in `Wait` state
    - When it receives an `onPropertyChangedEvent` event it switches to `End` state

## ChainDeployment policy

- While in `Start` state
    - It switches to `Ready` state
- While in `Ready` state
    - When it receives `onStart` event it sets the first set of properties
    - It switches to `Live` state
- While in `Live` state
    - When it receives an `onPropertyChangedEvent` event
        - If there are pending property updates it sends a new batch
        - If there are no more, it switches to `End` state
