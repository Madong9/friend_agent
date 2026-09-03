// services/auth.js — 兼容层：登录逻辑已统一收敛到 services/api.js
const api = require('./api.js');

module.exports = {
  ensureToken: api.ensureToken,
  login: api.wechatLogin,
};
