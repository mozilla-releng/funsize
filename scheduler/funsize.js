'use strict';
import taskcluster from 'taskcluster-client';
import {processMessage} from './lib/functions';
import config from './config/rail';
import {log} from './lib/logging';

function routingKeyPatterns() {
  let branches = [
    'mozilla-central',
    'mozilla-aurora',
    'comm-central',
    'comm-aurora'
  ];
  let platforms = [ 'linux', 'linux64', 'win32', 'win64', 'mac' ];
  let jobs = [];
  for (let branch of branches) {
    for (let platform of platforms) {
      jobs = jobs.concat([
        `build.${branch}-${platform}-nightly.*.finished`,
        `build.${branch}-${platform}-l10n-nightly.*.finished`
      ]);
    }
  }
  return jobs;
}

async function main() {
  let listener = new taskcluster.PulseListener(config.pulse);
  let scheduler = new taskcluster.Scheduler(config.taskcluster);

  let bindings = [];
  // TODO: Need to check if the bindings are only thiese ones
  for (let pattern of routingKeyPatterns()) {
    bindings.push(
      listener.bind({
        exchange: 'exchange/build/',
        routingKeyPattern: pattern
      })
    );
  }
  await Promise.all(bindings);

  listener.on('message', (message) => {
    return processMessage(message, scheduler);
  });

  log.info("Starting listener");
  await listener.resume();
}

main();
