import winston from 'winston';
import path from 'path';
import config from '../config/rail';

export var log = new (winston.Logger)(
  {transports: [
    new (winston.transports.Console)({
      timestamp: true,
      level: 'info',
      prettyPrint: true
    }),
    new (winston.transports.DailyRotateFile)({
      filename: path.join(config.funsize.logDir, "funsize.log"),
      level: 'debug',
      json: false,
      prettyPrint: true
    })
   ]
  }
);

