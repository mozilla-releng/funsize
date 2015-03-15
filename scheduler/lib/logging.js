import winston from 'winston';
import path from 'path';

export var log = new (winston.Logger)(
  {transports: [
    new (winston.transports.Console)({
      timestamp: true,
      level: 'info',
      prettyPrint: true
    }),
    new (winston.transports.DailyRotateFile)({
      filename: path.join(__dirname, "../logs/funsize.log"),
      level: 'debug',
      json: false,
      prettyPrint: true
    })
   ]
  }
);

