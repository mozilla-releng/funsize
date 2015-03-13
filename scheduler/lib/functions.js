'use strict';

import {fromNowJSON} from 'taskcluster-client/lib/utils';
import slugid from 'slugid';
import config from '../config/rail';
import _ from 'lodash';
import {BalrogClient} from './balrog';
import openpgp from 'openpgp';
import fs from 'fs';
import path from 'path';
import yaml from 'js-yaml';
import Mustache from 'mustache';
import Debug from 'debug';

const debug = Debug('funsize:functions');

var pubKeyArmored = fs.readFileSync(path.join(__dirname, '../docker-worker-pub.pem'), 'ascii');
var pubKey = openpgp.key.readArmored(pubKeyArmored);

async function encryptMessage (message) {

  let encryptedMessage = await openpgp.encryptMessage(pubKey.keys, message);
  var unarmoredEncryptedData = openpgp.armor.decode(encryptedMessage).data;
  return new Buffer(unarmoredEncryptedData).toString('base64');
}

async function encryptEnv(taskId, startTime, endTime, name, value) {
  let message = {
    messageVersion: "1",
    taskId: taskId,
    startTime: startTime,
    endTime: endTime,
    name: name,
    value: value
  };
  return await encryptMessage(JSON.stringify(message));
}

// TODO: compile the regexps only once
var interestingBuilderName = function (builderName){
  let branches = [
    'mozilla-central',
    'mozilla-aurora',
    'comm-central',
    'comm-aurora'
  ];
  let builders = [];
  for (let branch of branches) {
    builders = builders.concat([
      `WINNT \d+\.\d+ (x86-64 )?${branch} nightly`,
      `Linux (x86-64 )?${branch} nightly`,
      `OS X \d+\.\d+ ${branch} nightly`,
      `(Thunderbird|Firefox) ${branch} (linux|linux64|win32|win64|mac) l10n nightly`
    ]);
  }
  return builders.some(function(builder){
    return RegExp(builder).test(builderName);
  });
};

var propertiesToObject = function(props){
  return props.reduce(function(obj, prop){
    obj[prop[0]] = prop[1];
    return obj;
  }, {});
};

export async function processMessage(message, scheduler) {
  let payload = message.payload.payload;
  if (!interestingBuilderName(payload.build.builderName)) {
    console.log("ignoring", payload.build.builderName, message.routingKey);
    return;
  }
  if (payload.results !== 0) {
    console.log("ignoring %s/%s with non zero (%s) result",
                payload.build.builderName, message.routingKey,
                payload.results);
    return;
  }
  let props = propertiesToObject(payload.build.properties);
  let locale = props.locale || 'en-US';
  let platform = props.platform;
  let branch = props.branch;
  let product = props.appName;
  debug("Processign %s %s %s %s", product, branch, platform, locale);
  let c = new BalrogClient('https://aus4-admin.mozilla.org/api',
                           config.balrog.credentials);
  let releases = await c.getReleases(product, branch, {limit: 3});
  debug("Got releases %s", releases);
  let build_from = await c.getBuild(_.last(releases).name, platform, locale);
  debug("From: %s", build_from);
  let build_to = await c.getBuild(_.first(releases).name, platform, locale);
  debug("To: %s", build_from);
  let fromMAR = build_from["completes"][0]["fileUrl"];
  let toMAR = build_to["completes"][0]["fileUrl"];
  debug("Updates from %s to %s", fromMAR, toMAR);
  console.log("creatig task for", message.routingKey);
  await create_task_graph(scheduler, platform, locale, fromMAR, toMAR);
}

async function create_task_graph(scheduler, platform, locale, fromMAR, toMAR) {
  try {
  let template = fs.readFileSync(
    path.join(__dirname, '../tasks/funsize.yml'),
    {encoding: 'utf-8'}
  );
  let now = new Date();
  let vars = {
    updateGeneratorTaskId: slugid.v4(),
    signingTaskId: slugid.v4(),
    balrogTaskId: slugid.v4(),
    now: now.toJSON(),
    fromNowJSON: () => (text) => fromNowJSON(text),
    fromMAR: fromMAR,
    toMAR: toMAR,
    platform: platform,
    locale: locale,
  };
  let enc_deadline = now.getTime() + 24*3600*1000;
  vars.BALROG_USERNAME_ENC_MESSAGE = await encryptEnv(
    vars.balrogTaskId, now.getTime(), enc_deadline, 'BALROG_USERNAME',
    config.balrog.credentials.username);
  vars.BALROG_PASSWORD_ENC_MESSAGE = await encryptEnv(
    vars.balrogTaskId, now.getTime(), enc_deadline, 'BALROG_PASSWORD',
    config.balrog.credentials.password);
  let rendered = Mustache.render(template, vars);
  let taskGraph = yaml.safeLoad(rendered);
  let graphId = slugid.v4();
  console.log("Submitting a new graph", graphId);
  let result = await scheduler.createTaskGraph(graphId, taskGraph);
  console.log("Result was:", result.status);
  } catch (err) {
    console.log("eeeeew", err, err.stack);
    throw err;
  }
}
