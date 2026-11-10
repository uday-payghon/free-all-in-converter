const {defineConfig} = require('@playwright/test');
module.exports = defineConfig({
  testDir: './tests/browser', timeout: 60000, workers: 1,
  reporter: [['list'],['html',{open:'never'}]],
  use: {baseURL: process.env.BASE_URL || 'http://127.0.0.1:10000', trace:'retain-on-failure'},
  projects: [{name:'chromium',use:{browserName:'chromium'}},{name:'firefox',use:{browserName:'firefox'}},{name:'webkit',use:{browserName:'webkit'}}]
});
