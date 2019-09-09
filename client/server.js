var WebSocketServer = require('ws').Server;

var PORT = 8081;

var wss = new WebSocketServer({port: PORT});
var users = [];
var messages = [];
wss.on('connection', function (ws) {
  var isNewPerson = true;
  var username = null;
  for(var i=0;i<users.length;i++){
    if(users[i].username === ws.username){
      isNewPerson = false;
      break;
    }else{
      isNewPerson = true;
    }
  }
  if(isNewPerson){
    username = ws.username;
    users.push({
      username:ws.username
    })
   } 
  messages.forEach(function(message){
    ws.send(message);
  });
  ws.on('message', function (message) {
    messages.push(message);
    console.log('Message Received: %s', message);
    wss.clients.forEach(function (conn) {
      conn.send(message);
    });
  });
});