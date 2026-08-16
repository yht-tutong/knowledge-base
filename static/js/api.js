var API = (function() {
    var BASE = '/api';
    var _pending = 0;
    var _timer = null;

    function showLoading() {
        _pending++;
        if (_pending === 1) {
            // 200ms 后才显示，避免快速操作闪烁
            _timer = setTimeout(function() {
                var el = document.getElementById('loadingOverlay');
                if (el) el.classList.add('show');
            }, 200);
        }
    }

    function hideLoading() {
        _pending = Math.max(0, _pending - 1);
        if (_pending === 0) {
            clearTimeout(_timer);
            var el = document.getElementById('loadingOverlay');
            if (el) el.classList.remove('show');
        }
    }

    function request(url, options) {
        showLoading();
        options = options || {};
        var headers = options.headers || {};
        if (options.body && typeof options.body === 'string') {
            headers['Content-Type'] = 'application/json';
        }
        options.headers = headers;

        return fetch(url, options).then(function(res) {
            var ct = res.headers.get('content-type') || '';
            if (ct.indexOf('application/json') === -1) {
                return res.text().then(function(text) {
                    throw new Error('HTTP ' + res.status + ': ' + text.substring(0, 200));
                });
            }
            return res.json().then(function(body) {
                if (!res.ok || body.code !== 200) {
                    var err = new Error(body.message || '请求失败');
                    err.status = res.status;
                    err.data = body;
                    throw err;
                }
                return body.data;
            });
        }).finally(hideLoading).catch(function(err) {
            if (err.status === 401) {
                window.location.href = '/login';
            }
            throw err;
        });
    }

    function buildQueryString(params) {
        var parts = [];
        for (var key in params) {
            if (params.hasOwnProperty(key) && params[key] !== null && params[key] !== undefined && params[key] !== '') {
                parts.push(encodeURIComponent(key) + '=' + encodeURIComponent(params[key]));
            }
        }
        return parts.length > 0 ? '?' + parts.join('&') : '';
    }

    return {
        // 分类
        getCategories: function() {
            return request(BASE + '/categories');
        },

        createCategory: function(data) {
            return request(BASE + '/categories', {
                method: 'POST',
                body: JSON.stringify(data)
            });
        },

        deleteCategory: function(id) {
            return request(BASE + '/categories/' + id, {
                method: 'DELETE'
            });
        },

        updateCategory: function(id, data) {
            return request(BASE + '/categories/' + id, {
                method: 'PUT',
                body: JSON.stringify(data)
            });
        },

        // 知识点
        getKnowledgeList: function(params) {
            return request(BASE + '/knowledge' + buildQueryString(params));
        },

        createKnowledge: function(data) {
            return request(BASE + '/knowledge', {
                method: 'POST',
                body: JSON.stringify(data)
            });
        },

        getKnowledge: function(id) {
            return request(BASE + '/knowledge/' + id);
        },

        updateKnowledge: function(id, data) {
            return request(BASE + '/knowledge/' + id, {
                method: 'PUT',
                body: JSON.stringify(data)
            });
        },

        deleteKnowledge: function(id) {
            return request(BASE + '/knowledge/' + id, {
                method: 'DELETE'
            });
        },

        duplicateKnowledge: function(id) {
            return request(BASE + '/knowledge/' + id + '/duplicate', {
                method: 'POST'
            });
        },

        importKnowledge: function(data) {
            return request(BASE + '/knowledge/import', {
                method: 'POST',
                body: JSON.stringify(data)
            });
        },

        exportKnowledge: function(data) {
            return fetch(BASE + '/knowledge/export', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            }).then(function(res) {
                return res.json();
            }).then(function(body) {
                if (body.code !== 200) throw new Error(body.message || '导出失败');
                return body.data;
            });
        },

        // 标签
        getTags: function() {
            return request(BASE + '/tags');
        },

        createTag: function(data) {
            return request(BASE + '/tags', {
                method: 'POST',
                body: JSON.stringify(data)
            });
        },

        deleteTag: function(id) {
            return request(BASE + '/tags/' + id, {
                method: 'DELETE'
            });
        },

        deleteTags: function(ids) {
            return request(BASE + '/tags/batch_delete', {
                method: 'POST',
                body: JSON.stringify({ ids: ids })
            });
        },

        // 操作历史
        getOperations: function() {
            return request(BASE + '/operations');
        },
        undoOperation: function(id) {
            return request(BASE + '/operations/' + id + '/undo', { method: 'POST' });
        },
        undoAllOperations: function(id) {
            return request(BASE + '/operations/' + id + '/undo_all', { method: 'POST' });
        },

        // 备份管理
        getBackups: function() {
            return request(BASE + '/backups');
        },
        createBackup: function(note) {
            return request(BASE + '/backups', { method: 'POST', body: JSON.stringify({note: note || ''}) });
        },
        restoreBackup: function(filename) {
            return request(BASE + '/backups/' + encodeURIComponent(filename) + '/restore', { method: 'POST' });
        },
        deleteBackup: function(filename) {
            return request(BASE + '/backups/' + encodeURIComponent(filename), { method: 'DELETE' });
        },

        // 配置
        getConfig: function() {
            return request(BASE + '/config');
        },
        saveConfig: function(data) {
            return request(BASE + '/config', { method: 'POST', body: JSON.stringify(data) });
        }
    };
})();