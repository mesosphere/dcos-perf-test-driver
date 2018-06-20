/**
 * Define the closure that will be called when the PerfDriver API is injected
 * into the user's DOM. This will be called with the appropriate parameters so
 * whatever you export on the `userExports` will face the user, and whatever
 * you export on `driverExports` will face the PerfDriver.
 */
(function(userExports, driverExports) {
  const eventHandlers = {};
  const egressEventQueue = {
    queue: [],
    callback: enqueueMessageCallback
  };

  //////////////////////////////////////////////////////////////////////////////
  // Local Utility Functions
  //////////////////////////////////////////////////////////////////////////////

  /**
   * Local function to call an event callback on the user-facing API
   */
  function emitEvent() {
    const args = Arguments.from(arguments);
    const name = args.shift();
    if (eventHandlers[name] == null) return;
    eventHandlers[name].forEach(function(handler) {
      handler.apply(userExports, args);
    });
  }

  /**
   * Enqueue a message on the message queue
   *
   * The default method for sending an event is to just enqueue it
   * on the message queue
   */
  function enqueueMessageCallback(event) {
    egressEventQueue.queue.push(event);
  }

  //////////////////////////////////////////////////////////////////////////////
  // User-Facing API
  //////////////////////////////////////////////////////////////////////////////

  /**
   * Register an event listener on the global object, facing the user API
   */
  userExports.addEventListener = function(name, handler) {
    if (eventHandlers[name] == null) eventHandlers[name] = [];
    eventHandlers[name].push(handler);
  };

  /**
   * Remove an event listener from the global object, facing the user API
   */
  userExports.removeEventListener = function(name, handler) {
    if (eventHandlers[name] == null) return;
    const i = eventHandlers[name].indexOf(handler);
    if (i === -1) return;
    eventHandlers[name].splice(i, 1);
    if (eventHandlers[name].length === 0) delete eventHandlers[name];
  };

  /**
   * Send an event
   */
  userExports.send = function(name, data={}) {
    // Call out to the currently registered callback method.
    // If the queue is empty and we are waiting on `receive`, this is a
    // real-time operation. Otherwise we are pushing this event in the
    // message queue.
    egressEventQueue.callback(JSON.stringify({name, data}));
  }

  //////////////////////////////////////////////////////////////////////////////
  // Driver-Facing API
  //////////////////////////////////////////////////////////////////////////////

  /**
   * Pop an event from the user-facing event queue
   */
  driverExports.receive = function(callback) {
    // If there are events in the queue, return it now
    if (egressEventQueue.queue.length > 0) {
      callback(egressEventQueue.queue.shift());
      return;
    }

    // If the queue is empty, register a real-time callback
    egressEventQueue.callback = function(event) {
      // First replace the message callback with the default callback.
      egressEventQueue.callback = enqueueMessageCallback;
      // And then call out to the callback
      callback(event);
    }
  }

  /**
   * Send an event to the user-facing API
   */
  driverExports.emit = function(name, args) {
    if (eventHandlers[name] == null) return;
    eventHandlers[name].forEach(function(handler) {
      handler.apply(userExports, args);
    });
  }

}) /* Important: No tailing semi-colon !!!! */
