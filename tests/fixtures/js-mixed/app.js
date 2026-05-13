const express = require('express');
const { validationResult } = require('express-validator');

class Router {
    constructor() {
        this.router = express.Router();
    }

    get(path, handler) {
        this.router.get(path, this.wrap(handler));
    }

    post(path, handler) {
        this.router.post(path, this.wrap(handler));
    }

    wrap(handler) {
        return async (req, res, next) => {
            try {
                await handler(req, res, next);
            } catch (err) {
                next(err);
            }
        };
    }
}

function errorHandler(err, req, res, next) {
    console.error(err.stack);
    res.status(500).json({ error: err.message });
}

var legacyMode = false;
let appReady = false;

module.exports = { Router, errorHandler };
