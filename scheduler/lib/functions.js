'use strict';

//var Joi = require('joi');
var utils = require('taskcluster-client/lib/utils');
var slugid = require('slugid');
var config = require('../config/rail');

var interestingMessage = function (message){
  var routingKey = message.routingKey;
  var patterns = [
    // TODO: include en-US builds, chunked l10n
    /build\.mozilla-(central|aurora)-.+-l10n-nightly\..+\.finished/,
  ];
  return patterns.some(function(pattern){
    return pattern.test(routingKey);
  });
};

var propertiesToObject = function(props){
  return props.reduce(function(obj, prop){
    obj[prop[0]] = prop[1];
    return obj;
  }, {});
};

var processMessage = function(message, scheduler){
  if (!interestingMessage(message)) {
    console.log("ignoring", message.routingKey);
    return undefined;
  }
  var payload = message.payload.payload;
  var result = payload.results;
  if (result !== 0) {
    console.log("Ignoring non zero build", result);
    return undefined;
  }
  var props = propertiesToObject(payload.build.properties);
  //console.log(props.platform, props.completeMarUrl, props.completeMarHash,
  //            props.branch);
  var data = {
    toMarURL: 'tbd',
    fromMarURL: 'TBD', // get from balrog
    platform: 'TODO',
    locale: 'TODO',
  };
  triggerFunsizeTask(data, scheduler);
};

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
  console.log("almost");
  try {
    console.log("Submitting a new graph", graphId, JSON.stringify(tasks));
  } catch (e) {
    console.log("err", e);
  }
  //scheduler.createTaskGraph(graphId, tasks).then(function(result) {
  //  console.log(result.status);
  //  process.exit(1);
  //});
  console.log("done");
};

var createTaskDefinition = function(data, env){

  //var schema = Joi.object.keys({
    //toMarURL: Joi.string().required(),
    //toMarHash: Joi.string().required(),
    //fromMarURL: Joi.string().required(),
    //fromMarHash: Joi.string().required(),
    //productVersion: Joi.string().required(),
    //channelID: Joi.string().required(),
    //repo: Joi.string().required(),
    //revision: Joi.string().required(),
  //});
  //Joi.validate(data, schema);

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

module.exports.processMessage = processMessage;
