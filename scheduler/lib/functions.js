'use strict';

import utils from 'taskcluster-client/lib/utils';
import slugid from 'slugid';
import config from '../config/rail';
import _ from 'lodash';
import {BalrogClient} from './balrog';
import openpgp from 'openpgp';
import fs from 'fs';
import path from 'path';

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
  let c = new BalrogClient('https://aus4-admin.mozilla.org/api',
                           config.balrog.credentials);
  let releases = await c.getReleases(product, branch, {limit: 3});
  let build_from = await c.getBuild(_.last(releases).name, platform, locale);
  let build_to = await c.getBuild(_.first(releases).name, platform, locale);
  let mar_from = build_from["completes"][0]["fileUrl"];
  let mar_to = build_to["completes"][0]["fileUrl"];
  console.log("creatig task for", message.routingKey);
  await create_task_graph(scheduler, platform, locale, mar_from, mar_to);
}

var triggerFunsizeTask = function(data, scheduler){
  var tasks1 = createTaskDefinition(data);
  var task1Id = slugid.v4();
  var tasks2 = createTaskDefinition(data, {PARENT_TASK_ID: task1Id});
  var task2Id = slugid.v4();
  var tasks ={
    tasks: [
      {
        taskId: task1Id,
        requires: [],
        task: tasks1
      },
      {
        taskId: task2Id,
        requires: [task1Id],
        task: tasks2
      },
    ]
  };
  var graphId = slugid.v4();
  try {
    console.log("Submitting a new graph", graphId, JSON.stringify(tasks));
  } catch (e) {
    console.log("err", e);
  }
  //scheduler.createTaskGraph(graphId, tasks).then(function(result) {
  //  console.log(result.status);
  //  process.exit(1);
  //});
};

var createTaskDefinition = function(data, env){

  var payload = {
   image: config.worker.image,
   command: ['/runme.sh'],
   maxRunTime: 300,
   artifacts: {
     path: '/home/worker/artifacts/',
     type: 'directory',
     expires: utils.fromNow('8h'),

   },
   env: {
     'TO_MAR': data.toMarURL,
     'FROM_MAR': data.fromMarURL,
     'PLATFORM': data.platform,
     'LOCALE': data.locale,
   }
  };
  if (env) {
    for (var k in env) {
      if (env.hasOwnProperty(k)) {
        payload.env[k] = env[k];
      }
    }
  }
  var taskDef = {
    provisionerId: "aws-provisioner",
    workerType: config.worker.workerType,
    created: new Date().toJSON(),
    deadline: utils.fromNow('1h'),
    payload: payload,
    metadata: {
      name: "Funsize update generator task",
      description: "Funsize update generator task",
      owner: "release+funsize@mozilla.com",
      source: "https://github.com/mozilla/funsize-taskcluster",
    }
  };
  return taskDef;
};

async function create_task_graph(scheduler, platform, locale, from_mar, to_mar) {
  let task1Id = slugid.v4();
  let task2Id = slugid.v4();
  let task3Id = slugid.v4();
  let nowISO = (new Date()).toJSON();
  let now = _.now();
  let deadlineISO = utils.fromNow('2h');
  let deadline = _.now() + 2*3600*1000;
  let artifactsExpireISO = utils.fromNow('7d');

  let taskGraph = {
    scopes: ['queue:*', 'docker-worker:*', 'scheduler:*'],
    tasks: [
      {
        taskId: task1Id,
        requires: [],
        task:{
          provisionerId: "aws-provisioner",
          workerType: "b2gtest",
          created: nowISO,
          deadline: deadlineISO,
          payload: {
            image: "rail/funsize-update-generator",
            command: ["/runme.sh"],
            maxRunTime: 300,
            artifacts:{
              "public/env": {
                path: "/home/worker/artifacts/",
                type: "directory",
                expires: artifactsExpireISO,
              }
            },
            env: {
              FROM_MAR: from_mar,
              TO_MAR: to_mar,
              PLATFORM: platform,
              LOCALE: locale,
            }
          },
          metadata: {
            name: "Funsize update generator task",
            description: "Funsize update generator task",
            owner: "release+funsize@mozilla.com",
            source: "https://github.com/rail/funsize-taskcluster"
          }
        }
      },
      {
        taskId: task2Id,
        requires: [task1Id],
        task: {
          provisionerId: "aws-provisioner",
          workerType: "b2gtest",
          created: nowISO,
          deadline: deadlineISO,
          payload: {
            image: "rail/funsize-signer",
            command: ["/runme.sh"],
            maxRunTime: 300,
            artifacts: {
              "public/env": {
                path: "/home/worker/artifacts/",
                type: "directory",
                expires: artifactsExpireISO,
              }
            },
            env: {
              PARENT_TASK_ARTIFACTS_URL_PREFIX:
                  "https://queue.taskcluster.net/v1/task/" + task1Id + "/artifacts/public/env",
            }
          },
          metadata: {
            name: "Funsize signing task",
            description: "Funsize signing task",
            owner: "release+funsize@mozilla.com",
            source: "https://github.com/rail/funsize-taskcluster"
          }
        }
      },
      {
        taskId: task3Id,
        requires: [task2Id],
        task: {
          provisionerId: "aws-provisioner",
          workerType: "b2gtest",
          created: nowISO,
          deadline: deadlineISO,
          payload: {
            image: "rail/funsize-balrog-submitter",
            command: ["/runme.sh"],
            maxRunTime: 300,
            env: {
              PARENT_TASK_ARTIFACTS_URL_PREFIX:
                  "https://queue.taskcluster.net/v1/task/" + task2Id + "/artifacts/public/env",
              BALROG_API_ROOT: "https://aus4-admin-dev.allizom.org/api",
            },
            encryptedEnv: [
              await encryptEnv(task3Id, now, deadline, 'BALROG_USERNAME',
                         config.balrog.credentials.username),
              await encryptEnv(task3Id, now, deadline, 'BALROG_PASSWORD',
                         config.balrog.credentials.password)
            ],
          },
          metadata: {
            name: "Funsize balrog submitter task",
            description: "Funsize balrog submitter task",
            owner: "release+funsize@mozilla.com",
            source: "https://github.com/rail/funsize-taskcluster"
          }
        }
      },
    ],
    metadata: {
        name: "Funsize",
        description: "Funsize is **fun**!",
        owner: "rail@mozilla.com",
        source: "http://rail.merail.ca"
    }
  };
  let graphId = slugid.v4();
  console.log("Submitting a new graph", graphId);
  let result = await scheduler.createTaskGraph(graphId, taskGraph);
  console.log(result.status);
}
