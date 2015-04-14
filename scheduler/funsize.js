'use strict';
import taskcluster from 'taskcluster-client';
import {processMessage} from './lib/functions';
import {log, setLogDir} from './lib/logging';
import program from 'commander';
import fs from 'fs';

function routingKeyPatterns() {
  let branches = [
    'mozilla-central',
    'mozilla-aurora',
    // Thunderbird hasn't switched to mozharness yet
    // 'comm-central',
    // 'comm-aurora'
  ];
  let platforms = [ 'linux', 'linux64', 'win32', 'win64', 'macosx64' ];
  let jobs = [];
  for (let branch of branches) {
    for (let platform of platforms) {
      jobs = jobs.concat([
        `build.${branch}-${platform}-nightly.*.finished`,
        // TODO: find a better way to specify these
        `build.${branch}-${platform}-l10n-nightly-1.*.finished`,
        `build.${branch}-${platform}-l10n-nightly-2.*.finished`,
        `build.${branch}-${platform}-l10n-nightly-3.*.finished`,
        `build.${branch}-${platform}-l10n-nightly-4.*.finished`,
        `build.${branch}-${platform}-l10n-nightly-5.*.finished`,
        `build.${branch}-${platform}-l10n-nightly-6.*.finished`,
        `build.${branch}-${platform}-l10n-nightly-7.*.finished`,
        `build.${branch}-${platform}-l10n-nightly-8.*.finished`,
        `build.${branch}-${platform}-l10n-nightly-9.*.finished`,
        `build.${branch}-${platform}-l10n-nightly-10.*.finished`,
      ]);
    }
  }
  return jobs;
}

async function main() {
  program.
    option('-c, --config <config>', 'Configuration file').
    parse(process.argv);
  log.info("loading from", program.config);
  let config = require(program.config);
  log.info("config loaded from", program.config);
  if (config.funsize.logDir) {
    setLogDir(config.funsize.logDir);
  }
  let listener = new taskcluster.PulseListener(config.pulse);
  let scheduler = new taskcluster.Scheduler(config.taskcluster);

  let bindings = [];
  // TODO: Need to check if the bindings are only thiese ones
  for (let pattern of routingKeyPatterns()) {
    log.info(`Binding ${pattern}`);
    bindings.push(
      listener.bind({
        exchange: 'exchange/build/',
        routingKeyPattern: pattern
      })
    );
  }
  await Promise.all(bindings);

  listener.on('message', (message) => {
    return processMessage(message, scheduler, config);
  });

  log.info("Starting listener");
  await listener.resume();
}

main();
