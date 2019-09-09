document.addEventListener('DOMContentLoaded', init);

var SERVSOCK = new WebSocket('ws://localhost:8081');

var MESSAGES = []

var USERNAME = '';


function update_logs() {
    let log = d3.select('#chat-con')
      .selectAll('.logline')
      .data(MESSAGES);
    log.enter()
        .append('div')
        .classed('chat-item', true)
        .classed('item-left',true)
        .classed('logline', true)
        .text(d => d);
}
function update_logs_self() {
    let log = d3.select('#chat-con')
      .selectAll('.logline')
      .data(MESSAGES);
    log.enter()
        .append('div')
        .classed('chat-item', true)
        .classed('item-right',true)
        .classed('logline', true)
        .text(d => d);
}
function display_alert(msg){
  alert(msg)
}


function init() {
  d3.select('.login-btn')
    .on('click', () => {
      let name = d3.select('#loginName').property('value');
      USERNAME = name;
      SERVSOCK.send(JSON.stringify({'msgtype': 'REGISTER', 'sender': name}));
    });

  d3.select('.join-btn')
    .on('click', () => {
      let chan = d3.select('#channame').property('value');
      SERVSOCK.send(JSON.stringify({'msgtype': 'JOIN', 'destination': chan, 'sender': USERNAME}));
    });

  d3.select('.sendBtn')
    .on('click', () => {
      const chan = d3.select('#msgchannel').property('value');
      const content = d3.select('#content').property('value');
      if(content == 'q'){
        SERVSOCK.send(JSON.stringify({'msgtype': 'LEAVE', 'destination': chan, 'sender': USERNAME}));
      }
      const msg = JSON.stringify({
        'msgtype': 'MSG',
        'sender': USERNAME,
        'destination': chan,
        'content': content
      })
      SERVSOCK.send(msg);
      MESSAGES.push("["+chan+"] "+USERNAME+" : "+content);
      update_logs_self();
    })
  d3.select('.dis-btn')
    .on('click', () => {
      let chan = d3.select('#channame').property('value');
      SERVSOCK.send(JSON.stringify({'msgtype': 'LEAVE', 'destination': chan, 'sender': USERNAME}));
    })

  SERVSOCK.onopen = function(e) {
    $('.login-wrap').show('fast');
    $('.chat-wrap').hide('fast');
  }

  SERVSOCK.onerror = function(e) {
    console.log(e);
  }

  SERVSOCK.onclose = function(e) {

    console.log('Disconnected');
  }

  SERVSOCK.onmessage = function(e) {
    let msg = JSON.parse(e.data);

    if(msg.msgtype=='REGFAILED'){
      display_alert(msg.content+" is already exist!");

    }
    else if(msg.msgtype=='REGISTERED'){
      $('.login-wrap').hide('slow');
      $('.chat-wrap').show('slow');
      MESSAGES.push(msg.content);
    }
    else if(msg.msgtype=='JOINED'){
      MESSAGES.push('Members of current room:\n'+msg.content);
    }
    else if(msg.msgtype=='NOTICE'){
      MESSAGES.push(msg.sender+" have "+msg.content+" "+msg.destination)
    }
    else if(msg.msgtype=='MSG'){
      MESSAGES.push("["+msg.destination+"] "+msg.sender+" : "+msg.content)
    }
    else if(msg.msgtype=='ERROR'){
      MESSAGES.push(msg.content)
    }
    update_logs();
  }
}