# CloudBase JS SDK Mini Program runtime

These runtime bundles are the unmodified `miniprogram_dist` outputs from
`@cloudbase/js-sdk` v3.9.0:

- `app.js`
- `auth.js`
- `cloudrun.js`

They are vendored because the WeChat uploader can incorrectly remove lazily
loaded `miniprogram_npm` modules. The full `node_modules` and
`miniprogram_npm` trees remain excluded from release uploads.

Pinned SHA-256 values:

- app: `3874f62720b02ee0feb051bf3814ebf7762cf586da9dddf833dd24773a6b1a29`
- auth: `74454489023f2336745eafcd56a6691a604a3143b89ea1e621e6e7f3a19c8703`
- cloudrun: `d62d0fa658770d345036c00a631ec3039cc25393d6ac5aaf963ddc88d26d9cd7`

The upstream license is included as `LICENSE`.
