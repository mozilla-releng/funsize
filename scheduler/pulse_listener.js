'use strict';


var taskcluster = require('taskcluster-client');
var Promise = require('promise');
var functions = require('./lib/functions');
var config = require('./config/rail');

var listener = new taskcluster.PulseListener(config.pulse);
var scheduler = new taskcluster.Scheduler(config.taskcluster);

listener.bind({
  exchange: 'exchange/build/',
  routingKeyPattern: 'build.#.finished'
});

listener.on('message', function(message) {
  return new Promise(function(){
    functions.processMessage(message, scheduler);
    message.ack();
  });
});

listener.resume().then(function() {
  console.log("listening");
});
