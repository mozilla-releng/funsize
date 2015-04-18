var fs = require('fs');
var openpgp = require('openpgp');
//var base64 = require('openpgp/src/encoding/base64');
//var enums = require('openpgp/src/enums');

var pubKeyArmored = fs.readFileSync('docker-worker-pub.pem', 'ascii');
var pubKey = openpgp.key.readArmored(pubKeyArmored);

var message = new Buffer(process.argv[2], 'base64');
var encryptMessage = openpgp.encryptMessage(pubKey.keys, message.toString());
encryptMessage.then(function(encryptedMessage){
  var unarmoredEncryptedData = openpgp.armor.decode(encryptedMessage).data;
  var result = new Buffer(unarmoredEncryptedData).toString('base64');
  console.log(result);
}).catch(function(err){
  throw err;
});
