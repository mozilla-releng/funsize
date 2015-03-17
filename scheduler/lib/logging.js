import winston from 'winston';
import path from 'path';

export var log = new (winston.Logger)(
  {transports: [
    new (winston.transports.Console)({
      timestamp: true,
      level: process.env.FUNSIZE_LOG_LEVEL || 'info',
      prettyPrint: true
    })
   ]
  }
);

export function setLogDir(logDir) {
  log.add(winston.transports.DailyRotateFile, {
    filename: path.join(logDir, "funsize.log"),
    level: 'debug',
    json: false,
    prettyPrint: true
  });
}
