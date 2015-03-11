'use strict';
import taskcluster from 'taskcluster-client';
import {processMessage} from './lib/functions';
import config from './config/rail';

var listener = new taskcluster.PulseListener(config.pulse);
var scheduler = new taskcluster.Scheduler(config.taskcluster);

listener.bind({
  exchange: 'exchange/build/',
  routingKeyPattern: 'build.#.finished'
});

listener.on('message', function(message) {
  return new Promise(function() {
    processMessage(message, scheduler);
    message.ack();
  });
});

listener.resume().then(function() {
  console.log("listening");
});

process.on('uncaughtException', function (err) {
  console.error((new Date).toUTCString() + ' uncaughtException:', err.message);
  console.error(err.stack);
  process.exit(1);
});
