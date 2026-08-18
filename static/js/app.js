var App = (function() {
    // 状态管理
    var currentCategoryId = null;
    var currentKeyword = '';
    var currentTagFilterIds = [];
    var categories = [];
    var allTags = [];
    var selectedIds = {};
    var isDragging = false;
    var dragStartX = 0;
    var dragStartY = 0;
    var importData = null;
    var currentKnowledgeItems = [];

    // 渲染 Markdown 并在 DOM 中渲染 LaTeX 公式
    function renderMarkdownTo(el, content) {
        if (typeof marked !== 'undefined' && typeof marked.parse === 'function') {
            el.innerHTML = marked.parse(content);
            if (typeof renderMathInElement === 'function') {
                try {
                    renderMathInElement(el, {
                        delimiters: [
                            {left: '$$', right: '$$', display: true},
                            {left: '$', right: '$', display: false}
                        ],
                        throwOnError: false
                    });
                } catch(e) {
                    // KaTeX 渲染失败，保留 marked 渲染的纯文本
                }
            }
        } else {
            el.innerHTML = '<pre style="white-space:pre-wrap;word-break:break-word;font-family:inherit;">' + escapeHtml(content) + '</pre>';
        }
    }

    // ==================== 初始化 ====================
    function init() {
        // 重启后自动登录：消耗 restart_token（如果会话仍有效）
        var restartToken = localStorage.getItem('restart_token');
        if (restartToken) {
            localStorage.removeItem('restart_token');
            fetch('/auth/restart-login', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({token: restartToken})
            }).catch(function() {});
        }

        // 搜索
        document.getElementById('searchInput').addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                currentKeyword = this.value.trim();
                loadKnowledgeList();
            }
        });

        document.getElementById('searchBtn').addEventListener('click', function() {
            currentKeyword = document.getElementById('searchInput').value.trim();
            loadKnowledgeList();
        });

        // "全部分类" 点击事件
        var allCategoryLink = document.querySelector('.category-item[data-category-id=""]');
        if (allCategoryLink) {
            allCategoryLink.addEventListener('click', function(e) {
                e.preventDefault();
                currentCategoryId = null;
                currentKeyword = '';
                document.getElementById('searchInput').value = '';
                var allItems = document.querySelectorAll('.category-nav .category-item');
                for (var i = 0; i < allItems.length; i++) {
                    allItems[i].classList.remove('active');
                }
                this.classList.add('active');
                clearSelection();
                loadKnowledgeList();
            });
        }

        // 新增/编辑模态框
        document.getElementById('addBtn').addEventListener('click', showAddModal);
        document.getElementById('modalClose').addEventListener('click', closeModal);
        document.getElementById('cancelBtn').addEventListener('click', closeModal);
        document.getElementById('modalOverlay').addEventListener('click', function(e) {
            if (e.target === this) closeModal();
        });
        document.getElementById('knowledgeForm').addEventListener('submit', function(e) {
            e.preventDefault();
            submitKnowledge();
        });

        // 图片上传
        document.getElementById('btnUploadImage').addEventListener('click', function() {
            document.getElementById('imageInput').click();
        });
        document.getElementById('imageInput').addEventListener('change', function() {
            var file = this.files[0];
            if (!file) return;
            var formData = new FormData();
            formData.append('image', file);
            fetch('/api/upload', { method: 'POST', body: formData })
                .then(function(res) { return res.json(); })
                .then(function(data) {
                    if (data.code === 200) {
                        var textarea = document.getElementById('knowledgeContent');
                        var url = data.data.url;
                        textarea.value += '\n![' + file.name + '](' + url + ')\n';
                        showToast('图片已插入', 'success');
                    } else {
                        showToast('上传失败: ' + data.message, 'error');
                    }
                }).catch(function() {
                    showToast('上传失败', 'error');
                });
        });

        // 附件上传
        document.getElementById('btnUploadFile').addEventListener('click', function() {
            document.getElementById('fileInput').click();
        });
        document.getElementById('fileInput').addEventListener('change', function() {
            var file = this.files[0];
            if (!file) return;
            var formData = new FormData();
            formData.append('file', file);
            fetch('/api/upload', { method: 'POST', body: formData })
                .then(function(res) { return res.json(); })
                .then(function(data) {
                    if (data.code === 200) {
                        var textarea = document.getElementById('knowledgeContent');
                        var markdown = data.data.markdown;
                        textarea.value += '\n' + markdown + '\n';
                        showToast('附件已插入', 'success');
                    } else {
                        showToast('上传失败: ' + data.message, 'error');
                    }
                }).catch(function() {
                    showToast('上传失败', 'error');
                });
        });

        // MD 预览切换
        document.getElementById('btnPreviewMD').addEventListener('click', function() {
            var preview = document.getElementById('mdPreview');
            var textarea = document.getElementById('knowledgeContent');
            if (preview.style.display === 'none') {
                preview.style.display = 'block';
                textarea.style.display = 'none';
                this.textContent = '编辑';
                renderMarkdownTo(preview, textarea.value || '');
            } else {
                preview.style.display = 'none';
                textarea.style.display = 'block';
                this.textContent = '预览';
            }
        });

        // 导入/导出
        document.getElementById('importBtn').addEventListener('click', showImportModal);
        document.getElementById('exportBtn').addEventListener('click', function() {
            exportSelected('json');
        });

        // 批量操作栏
        document.getElementById('btnSelectAll').addEventListener('click', selectAll);
        document.getElementById('btnInvertSelect').addEventListener('click', invertSelection);
        document.getElementById('btnClearSelect').addEventListener('click', clearSelection);
        document.getElementById('btnBatchDelete').addEventListener('click', deleteSelected);
        document.getElementById('btnExportJson').addEventListener('click', function() { exportSelected('json'); });
        document.getElementById('btnExportTxt').addEventListener('click', function() { showExportModal(); });

        // 导出 TXT 选项模态框
        document.getElementById('exportModalClose').addEventListener('click', closeExportModal);
        document.getElementById('exportCancelBtn').addEventListener('click', closeExportModal);
        document.getElementById('exportModalOverlay').addEventListener('click', function(e) {
            if (e.target === this) closeExportModal();
        });
        document.getElementById('exportConfirmBtn').addEventListener('click', confirmExport);

        // 标签管理
        document.getElementById('btnTagManage').addEventListener('click', showTagModal);
        document.getElementById('tagModalClose').addEventListener('click', closeTagModal);
        document.getElementById('tagModalOverlay').addEventListener('click', function(e) {
            if (e.target === this) closeTagModal();
        });
        document.getElementById('btnAddTag').addEventListener('click', addTag);
        document.getElementById('newTagName').addEventListener('keydown', function(e) {
            if (e.key === 'Enter') { e.preventDefault(); addTag(); }
        });

        // 确认弹窗关闭
        document.getElementById('confirmModalOverlay').addEventListener('click', function(e) {
            if (e.target === this) {
                this.classList.remove('show');
            }
        });

        // 分类管理
        document.getElementById('btnAddCategory').addEventListener('click', addCategory);
        document.getElementById('newCategoryName').addEventListener('keydown', function(e) {
            if (e.key === 'Enter') { e.preventDefault(); addCategory(); }
        });

        // 标签筛选（多选模式）
        document.getElementById('tagFilterArea').addEventListener('click', function(e) {
            var item = e.target.closest('.tag-filter-item');
            if (!item) return;
            var tagId = item.getAttribute('data-tag-id');
            var idx = currentTagFilterIds.indexOf(tagId);
            if (idx >= 0) {
                currentTagFilterIds.splice(idx, 1);
            } else {
                currentTagFilterIds.push(tagId);
            }
            renderTagFilters();
            loadKnowledgeList();
        });

        // 操作历史
        document.getElementById('btnHistory').addEventListener('click', showHistoryModal);
        document.getElementById('btnBackup').addEventListener('click', showBackupModal);
        document.getElementById('historyModalClose').addEventListener('click', function() {
            document.getElementById('historyModalOverlay').classList.remove('show');
        });
        document.getElementById('backupModalClose').addEventListener('click', function() {
            document.getElementById('backupModalOverlay').classList.remove('show');
        });
        document.getElementById('btnCreateBackup').addEventListener('click', function() {
            var note = document.getElementById('backupNote').value.trim();
            API.createBackup(note).then(function() {
                showToast('备份创建成功', 'success');
                document.getElementById('backupNote').value = '';
                loadBackups();
            }).catch(function(err) {
                showToast('备份失败: ' + (err.message || '请重试'), 'error');
            });
        });

        // 历史模态框点击遮罩关闭
        document.getElementById('historyModalOverlay').addEventListener('click', function(e) {
            if (e.target === this) this.classList.remove('show');
        });
        document.getElementById('backupModalOverlay').addEventListener('click', function(e) {
            if (e.target === this) this.classList.remove('show');
        });

        // 日志查看
        document.getElementById('btnLogs').addEventListener('click', showLogModal);
        document.getElementById('logModalClose').addEventListener('click', function() {
            document.getElementById('logModalOverlay').classList.remove('show');
        });
        document.getElementById('logModalOverlay').addEventListener('click', function(e) {
            if (e.target === this) this.classList.remove('show');
        });

        // 设置
        document.getElementById('btnSettings').addEventListener('click', showSettingsModal);
        document.getElementById('settingsModalClose').addEventListener('click', closeSettingsModal);
        document.getElementById('settingsCancelBtn').addEventListener('click', closeSettingsModal);
        document.getElementById('settingsModalOverlay').addEventListener('click', function(e) {
            if (e.target === this) closeSettingsModal();
        });
        document.getElementById('settingsSaveBtn').addEventListener('click', saveSettings);
        document.getElementById('settingsDisableLogin').addEventListener('change', updateLoginSubOptions);
        document.querySelectorAll('input[name="passwordMode"]').forEach(function(el) {
            el.addEventListener('change', updatePasswordMode);
        });
        document.getElementById('btnClearCache').addEventListener('click', showCacheModal);
        document.getElementById('btnReset').addEventListener('click', showResetModal);
        document.getElementById('resetModalClose').addEventListener('click', closeResetModal);
        document.getElementById('resetCancelBtn').addEventListener('click', closeResetModal);
        document.getElementById('resetModalOverlay').addEventListener('click', function(e) {
            if (e.target === this) closeResetModal();
        });
        document.getElementById('resetConfirmBtn').addEventListener('click', resetSystem);
        document.getElementById('cacheModalClose').addEventListener('click', closeCacheModal);
        document.getElementById('cacheCancelBtn').addEventListener('click', closeCacheModal);
        document.getElementById('cacheModalOverlay').addEventListener('click', function(e) {
            if (e.target === this) closeCacheModal();
        });
        document.getElementById('cacheConfirmBtn').addEventListener('click', clearCache);
        document.getElementById('btnRestart').addEventListener('click', showRestartModal);
        document.getElementById('restartModalClose').addEventListener('click', closeRestartModal);
        document.getElementById('restartCancelBtn').addEventListener('click', closeRestartModal);
        document.getElementById('restartModalOverlay').addEventListener('click', function(e) {
            if (e.target === this) closeRestartModal();
        });
        document.getElementById('restartConfirmBtn').addEventListener('click', restartSystem);

        // 详情弹窗
        document.getElementById('detailModalClose').addEventListener('click', closeDetailModal);
        document.getElementById('detailModalOverlay').addEventListener('click', function(e) {
            if (e.target === this) closeDetailModal();
        });

        // 导入模态框
        document.getElementById('importModalClose').addEventListener('click', closeImportModal);
        document.getElementById('importCancelBtn').addEventListener('click', closeImportModal);
        document.getElementById('importModalOverlay').addEventListener('click', function(e) {
            if (e.target === this) closeImportModal();
        });
        document.getElementById('btnConfirmImport').addEventListener('click', confirmImport);
        document.getElementById('btnCopyPrompt').addEventListener('click', copyPrompt);

        // 粘贴解析
        document.getElementById('btnParsePaste').addEventListener('click', function() {
            var text = document.getElementById('importPasteArea').value.trim();
            if (!text) { showToast('请粘贴 JSON 内容', 'warning'); return; }
            try {
                importData = JSON.parse(text);
                document.getElementById('importPreview').value = JSON.stringify(importData, null, 2);
                document.getElementById('btnConfirmImport').disabled = false;
                showToast('解析成功，共 ' + (Array.isArray(importData) ? importData.length : 1) + ' 条', 'success');
            } catch (err) {
                showToast('JSON 解析失败: ' + err.message, 'error');
            }
        });

        // 文件上传
        var fileUploadArea = document.getElementById('fileUploadArea');
        fileUploadArea.addEventListener('click', function() {
            document.getElementById('importFileInput').click();
        });
        fileUploadArea.addEventListener('dragover', function(e) {
            e.preventDefault();
            this.classList.add('drag-over');
        });
        fileUploadArea.addEventListener('dragleave', function() {
            this.classList.remove('drag-over');
        });
        fileUploadArea.addEventListener('drop', function(e) {
            e.preventDefault();
            this.classList.remove('drag-over');
            var file = e.dataTransfer.files[0];
            if (file) handleFile(file);
        });
        document.getElementById('importFileInput').addEventListener('change', function() {
            var file = this.files[0];
            if (file) handleFile(file);
        });

        // 拖拽选择
        var knowledgeList = document.getElementById('knowledgeList');
        knowledgeList.addEventListener('mousedown', onDragStart);
        document.addEventListener('mousemove', onDragMove);
        document.addEventListener('mouseup', onDragEnd);

        // 汉堡菜单（移动端）
        var hamburgerBtn = document.getElementById('hamburgerBtn');
        var sidebar = document.querySelector('.sidebar');
        var sidebarOverlay = document.getElementById('sidebarOverlay');

        if (hamburgerBtn) {
            hamburgerBtn.addEventListener('click', function() {
                sidebar.classList.toggle('open');
                sidebarOverlay.classList.toggle('show');
            });
        }
        if (sidebarOverlay) {
            sidebarOverlay.addEventListener('click', function() {
                sidebar.classList.remove('open');
                sidebarOverlay.classList.remove('show');
            });
        }

        // 初始加载
        loadCategories();
        loadTags();
        loadKnowledgeList();
    }

    // ==================== 工具函数 ====================
    function getTagColor(tagName) {
        // 基于标签名 hash 映射到固定色盘
        var palette = [
            '#4a90d9', '#27ae60', '#e67e22', '#9b59b6', '#1abc9c',
            '#e74c3c', '#2c3e50', '#f39c12', '#2980b9', '#8e44ad',
            '#16a085', '#c0392b', '#d35400', '#7f8c8d', '#2ecc71'
        ];
        var hash = 0;
        for (var i = 0; i < tagName.length; i++) {
            hash = ((hash << 5) - hash) + tagName.charCodeAt(i);
            hash |= 0;
        }
        return palette[Math.abs(hash) % palette.length];
    }

    function formatTime(dateStr) {
        if (!dateStr) return '--';
        // 直接解析 "YYYY-MM-DD HH:MM:SS" 格式，不做时区转换
        var match = /^(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})/.exec(dateStr);
        if (match) {
            return match[1] + '-' + match[2] + '-' + match[3] + ' ' + match[4] + ':' + match[5];
        }
        return dateStr;
    }

    function escapeHtml(str) {
        if (!str) return '';
        var div = document.createElement('div');
        div.appendChild(document.createTextNode(str));
        return div.innerHTML;
    }

    function showToast(message, type) {
        type = type || 'success';
        var container = document.getElementById('toastContainer');
        var toast = document.createElement('div');
        toast.className = 'toast toast-' + type;
        toast.textContent = message;
        container.appendChild(toast);
        setTimeout(function() {
            toast.style.animation = 'toastFadeOut 0.3s ease forwards';
            setTimeout(function() {
                if (toast.parentNode) toast.parentNode.removeChild(toast);
            }, 300);
        }, 3000);
    }

    function showConfirm(message, callback) {
        document.getElementById('confirmMessage').textContent = message;
        document.getElementById('confirmModalOverlay').classList.add('show');

        var okBtn = document.getElementById('confirmOkBtn');
        var cancelBtn = document.getElementById('confirmCancelBtn');
        var cleanup = function() {
            document.getElementById('confirmModalOverlay').classList.remove('show');
            okBtn.removeEventListener('click', onOk);
            cancelBtn.removeEventListener('click', onCancel);
        };
        var onOk = function() { cleanup(); callback(true); };
        var onCancel = function() { cleanup(); callback(false); };
        okBtn.addEventListener('click', onOk);
        cancelBtn.addEventListener('click', onCancel);
    }

    // ==================== 分类 ====================
    function loadCategories() {
        API.getCategories().then(function(data) {
            categories = data || [];
            renderCategories();
        }).catch(function(err) {
            console.error('加载分类失败:', err);
            categories = [];
            renderCategories();
        });
    }

    function renderCategories() {
        var container = document.getElementById('categoryList');
        var html = '';

        for (var i = 0; i < categories.length; i++) {
            var cat = categories[i];
            var count = cat.knowledge_count !== undefined ? cat.knowledge_count : 0;
            html += '<a href="#" class="category-item" data-category-id="' + cat.id + '">' +
                '<span class="category-name">' + escapeHtml(cat.name) + '</span>' +
                '<input class="cat-edit-input" value="' + escapeHtml(cat.name) + '" data-cat-id="' + cat.id + '">' +
                '<span class="category-count">' + count + '</span>' +
                '<span class="cat-actions">' +
                    '<button type="button" class="cat-action-btn cat-edit" data-cat-id="' + cat.id + '" title="编辑">&#9998;</button>' +
                    '<button type="button" class="cat-action-btn cat-delete" data-cat-id="' + cat.id + '" title="删除">&times;</button>' +
                '</span>' +
                '</a>';
        }

        container.innerHTML = html;

        // 点击分类跳转
        var allItems = container.parentElement.querySelectorAll('.category-item');
        for (var j = 0; j < allItems.length; j++) {
            allItems[j].addEventListener('click', function(e) {
                // 不拦截按钮点击
                if (e.target.closest('button') || e.target.closest('input')) return;
                e.preventDefault();
                var id = this.getAttribute('data-category-id');
                currentCategoryId = id || null;
                currentKeyword = '';
                document.getElementById('searchInput').value = '';

                var allItems2 = document.querySelectorAll('.category-nav .category-item');
                for (var k = 0; k < allItems2.length; k++) {
                    allItems2[k].classList.remove('active');
                }
                this.classList.add('active');

                // 移动端点击分类后关闭侧边栏
                if (window.innerWidth <= 768) {
                    var sidebarEl = document.querySelector('.sidebar');
                    var overlayEl = document.getElementById('sidebarOverlay');
                    if (sidebarEl) sidebarEl.classList.remove('open');
                    if (overlayEl) overlayEl.classList.remove('show');
                }

                clearSelection();
                loadKnowledgeList();
            });
            // Drag and drop to category
            allItems[j].addEventListener('dragover', function(e) {
                e.preventDefault();
                e.dataTransfer.dropEffect = 'move';
                this.classList.add('drag-over');
            });
            allItems[j].addEventListener('dragleave', function() {
                this.classList.remove('drag-over');
            });
            allItems[j].addEventListener('drop', function(e) {
                e.preventDefault();
                this.classList.remove('drag-over');
                var kpId = parseInt(e.dataTransfer.getData('text/plain'), 10);
                var catId = this.getAttribute('data-category-id');
                if (!catId || !kpId) return;
                API.updateKnowledge(kpId, { category_id: parseInt(catId, 10) }).then(function() {
                    showToast('已移动到分类', 'success');
                    loadKnowledgeList();
                    loadCategories();
                }).catch(function(err) {
                    showToast('移动失败: ' + (err.message || '请重试'), 'error');
                });
            });
        }

        // 编辑按钮
        var editBtns = container.querySelectorAll('.cat-action-btn.cat-edit');
        for (var m = 0; m < editBtns.length; m++) {
            editBtns[m].addEventListener('click', function(e) {
                e.stopPropagation();
                e.preventDefault();
                var catId = parseInt(this.getAttribute('data-cat-id'), 10);
                startEditCategory(catId);
            });
        }

        // 删除按钮
        var delBtns = container.querySelectorAll('.cat-action-btn.cat-delete');
        for (var n = 0; n < delBtns.length; n++) {
            delBtns[n].addEventListener('click', function(e) {
                e.stopPropagation();
                e.preventDefault();
                var catId = parseInt(this.getAttribute('data-cat-id'), 10);
                deleteCategory(catId);
            });
        }
    }

    function startEditCategory(catId) {
        var item = document.querySelector('.category-item[data-category-id="' + catId + '"]');
        if (!item) return;
        item.classList.add('editing');
        var input = item.querySelector('.cat-edit-input');
        input.focus();
        input.select();

        var saveEdit = function() {
            var newName = input.value.trim();
            item.classList.remove('editing');
            input.removeEventListener('blur', saveEdit);
            input.removeEventListener('keydown', onKey);
            if (newName && newName !== getCategoryName(catId)) {
                API.updateCategory(catId, { name: newName }).then(function() {
                    loadCategories();
                    showToast('分类已更新', 'success');
                }).catch(function(err) {
                    showToast('更新失败: ' + (err.message || '请重试'), 'error');
                });
            }
        };

        var onKey = function(e) {
            if (e.key === 'Enter') { e.preventDefault(); saveEdit(); }
            if (e.key === 'Escape') { item.classList.remove('editing'); }
        };

        input.addEventListener('blur', saveEdit);
        input.addEventListener('keydown', onKey);
    }

    function getCategoryName(catId) {
        for (var i = 0; i < categories.length; i++) {
            if (categories[i].id === catId) return categories[i].name;
        }
        return '';
    }

    function deleteCategory(catId) {
        var name = getCategoryName(catId);
        if (name === '未分类') {
            showToast('「未分类」不可删除', 'warning');
            return;
        }
        showConfirm('确定要删除分类「' + name + '」吗？', function(ok) {
            if (!ok) return;
            API.deleteCategory(catId).then(function() {
                if (currentCategoryId === String(catId)) {
                    currentCategoryId = null;
                }
                loadCategories();
                loadKnowledgeList();
                showToast('分类已删除', 'success');
            }).catch(function(err) {
                showToast('删除失败: ' + (err.message || '请重试'), 'error');
            });
        });
    }

    function addCategory() {
        var name = document.getElementById('newCategoryName').value.trim();
        if (!name) { showToast('请输入分类名称', 'warning'); return; }
        API.createCategory({ name: name, description: '' }).then(function() {
            document.getElementById('newCategoryName').value = '';
            loadCategories();
            showToast('分类已添加', 'success');
        }).catch(function(err) {
            showToast('添加失败: ' + (err.message || '请重试'), 'error');
        });
    }

    // ==================== 标签管理 ====================
    function loadTags() {
        API.getTags().then(function(data) {
            allTags = data || [];
            renderTagFilters();
            renderTagCheckboxes();
            renderTagManageList();
        }).catch(function(err) {
            console.error('加载标签失败:', err);
            allTags = [];
            renderTagFilters();
            renderTagCheckboxes();
            renderTagManageList();
        });
    }

    function renderTagFilters() {
        var container = document.getElementById('tagFilterArea');
        if (allTags.length === 0) {
            container.innerHTML = '<div class="tag-filter-empty">暂无标签</div>';
            return;
        }
        var html = '';
        for (var i = 0; i < allTags.length; i++) {
            var tag = allTags[i];
            var activeClass = (currentTagFilterIds.indexOf(String(tag.id)) >= 0) ? ' active' : '';
            var shape = tag.shape || 'ellipse';
            var borderRadius = shape === 'ellipse' ? '12px' : '2px';
            var color = tag.color || getTagColor(tag.name);
            html += '<span class="tag-filter-item' + activeClass + '" data-tag-id="' + tag.id + '"' +
                ' style="background:' + color + '33;color:' + color + ';border:1px solid ' + color + ';border-radius:' + borderRadius + '">' +
                escapeHtml(tag.name) + '</span>';
        }
        container.innerHTML = html;
    }

    function renderTagCheckboxes() {
        var container = document.getElementById('tagCheckboxGrid');
        if (allTags.length === 0) {
            container.innerHTML = '<div class="tag-checkbox-empty">暂无标签，请先在标签管理中创建</div>';
            return;
        }
        var html = '';
        for (var i = 0; i < allTags.length; i++) {
            var tag = allTags[i];
            var shape = tag.shape || 'ellipse';
            var borderRadius = shape === 'ellipse' ? '12px' : '2px';
            var color = tag.color || getTagColor(tag.name);
            html += '<label class="tag-checkbox-item">' +
                '<input type="checkbox" value="' + tag.id + '" class="tag-checkbox">' +
                '<span class="tag-preview" style="background:' + color + '33;color:' + color + ';border:1px solid ' + color + ';border-radius:' + borderRadius + '">' + escapeHtml(tag.name) + '</span>' +
                '</label>';
        }
        container.innerHTML = html;
    }

    function getCheckedTagIds() {
        var checkboxes = document.querySelectorAll('#tagCheckboxGrid .tag-checkbox:checked');
        var ids = [];
        for (var i = 0; i < checkboxes.length; i++) {
            ids.push(parseInt(checkboxes[i].value, 10));
        }
        return ids;
    }

    function setCheckedTagIds(tagIds) {
        var checkboxes = document.querySelectorAll('#tagCheckboxGrid .tag-checkbox');
        var idSet = {};
        if (tagIds) {
            for (var i = 0; i < tagIds.length; i++) {
                idSet[tagIds[i]] = true;
            }
        }
        for (var j = 0; j < checkboxes.length; j++) {
            checkboxes[j].checked = !!idSet[parseInt(checkboxes[j].value, 10)];
        }
    }

    function showTagModal() {
        document.getElementById('tagModalOverlay').classList.add('show');
        document.getElementById('newTagName').value = '';
        renderTagManageList();
    }

    function closeTagModal() {
        document.getElementById('tagModalOverlay').classList.remove('show');
    }

    function addTag() {
        var name = document.getElementById('newTagName').value.trim();
        var shape = document.getElementById('newTagShape').value;
        var color = document.getElementById('newTagColor').value;

        if (!name) {
            showToast('请输入标签名称', 'warning');
            return;
        }

        API.createTag({ name: name, shape: shape, color: color }).then(function() {
            document.getElementById('newTagName').value = '';
            loadTags();
        }).catch(function(err) {
            console.error('创建标签失败:', err);
            showToast('创建标签失败: ' + (err.message || '请重试'), 'error');
        });
    }

    function deleteTag(id) {
        showConfirm('确定要删除该标签吗？', function(ok) {
            if (!ok) return;
            API.deleteTag(id).then(function() {
                loadTags();
            }).catch(function(err) {
                console.error('删除标签失败:', err);
                showToast('删除标签失败: ' + (err.message || '请重试'), 'error');
            });
        });
    }

    function renderTagManageList() {
        var container = document.getElementById('tagManageList');
        if (allTags.length === 0) {
            container.innerHTML = '<div class="tag-manage-empty">暂无标签</div>';
            return;
        }
        var html = '';
        for (var i = 0; i < allTags.length; i++) {
            var tag = allTags[i];
            var shape = tag.shape || 'ellipse';
            var shapeLabel = shape === 'ellipse' ? '椭圆' : '矩形';
            var borderRadius = shape === 'ellipse' ? '12px' : '2px';
            var color = tag.color || getTagColor(tag.name);
            html += '<div class="tag-manage-item">' +
                '<input type="checkbox" class="tag-manage-checkbox" value="' + tag.id + '">' +
                '<span class="tag-preview" style="background:' + color + '33;color:' + color + ';border:1px solid ' + color + ';border-radius:' + borderRadius + '">' + escapeHtml(tag.name) + '</span>' +
                '<span style="font-size:11px;color:#999;">(' + shapeLabel + ')</span>' +
                '<button class="tag-manage-delete" data-tag-id="' + tag.id + '">&times;</button>' +
                '</div>';
        }
        html += '<div style="margin-top:12px;width:100%;">' +
            '<button class="btn btn-danger btn-sm" id="btnBatchDeleteTags" style="width:100%;">批量删除选中标签</button>' +
            '</div>';
        container.innerHTML = html;

        var deleteBtns = container.querySelectorAll('.tag-manage-delete');
        for (var j = 0; j < deleteBtns.length; j++) {
            deleteBtns[j].addEventListener('click', function(e) {
                e.stopPropagation();
                var tagId = parseInt(this.getAttribute('data-tag-id'), 10);
                deleteTag(tagId);
            });
        }

        var batchBtn = document.getElementById('btnBatchDeleteTags');
        if (batchBtn) {
            batchBtn.addEventListener('click', function() {
                var checkboxes = document.querySelectorAll('#tagManageList .tag-manage-checkbox:checked');
                var ids = [];
                for (var k = 0; k < checkboxes.length; k++) {
                    ids.push(parseInt(checkboxes[k].value, 10));
                }
                if (ids.length === 0) {
                    showToast('请先选择要删除的标签', 'warning');
                    return;
                }
                showConfirm('确定要删除选中的 ' + ids.length + ' 个标签吗？', function(ok) {
                    if (!ok) return;
                    API.deleteTags(ids).then(function() {
                        loadTags();
                        showToast('已删除 ' + ids.length + ' 个标签', 'success');
                    }).catch(function(err) {
                        console.error('批量删除标签失败:', err);
                        showToast('批量删除标签失败: ' + (err.message || '请重试'), 'error');
                    });
                });
            });
        }
    }

    // ==================== 知识点列表 ====================
    function loadKnowledgeList() {
        var listEl = document.getElementById('knowledgeList');
        listEl.innerHTML = '<div class="empty-state">加载中...</div>';

        var params = {};
        if (currentCategoryId) {
            params.category_id = currentCategoryId;
        }
        if (currentKeyword) {
            params.keyword = currentKeyword;
        }
        if (currentTagFilterIds.length > 0) {
            params.tag_ids = currentTagFilterIds.join(',');
        }

        API.getKnowledgeList(params).then(function(data) {
            var items = (data && data.items) || [];
            currentKnowledgeItems = items;
            if (items.length === 0) {
                listEl.innerHTML = '<div class="empty-state">暂无知识点</div>';
                return;
            }

            var html = '';
            for (var i = 0; i < items.length; i++) {
                html += renderKnowledgeCard(items[i], i);
            }
            listEl.innerHTML = html;

            bindCardEvents();
            updateBatchToolbar();
        }).catch(function(err) {
            console.error('加载知识点列表失败:', err);
            listEl.innerHTML = '<div class="empty-state">加载失败，请重试</div>';
        });
    }

    function renderKnowledgeCard(kp, index) {
        var title = escapeHtml(kp.title || '无标题');
        var rawContent = kp.content || '';
        // 检测是否包含 markdown 语法
        var hasMarkdown = /[#*\-_>`~\[\]|!]/.test(rawContent);
        var content;
        if (hasMarkdown && typeof marked !== 'undefined' && typeof marked.parse === 'function') {
            try {
                // 用 marked 渲染后去除 HTML 标签，取纯文本前 100 字符
                var html = marked.parse(rawContent);
                var tmp = document.createElement('div');
                tmp.innerHTML = html;
                content = (tmp.textContent || tmp.innerText || '').replace(/\s+/g, ' ').trim();
                if (content.length > 100) {
                    content = content.substring(0, 100) + '...';
                }
                content = escapeHtml(content);
            } catch (e) {
                content = rawContent.length > 100 ? rawContent.substring(0, 100) + '...' : rawContent;
                content = escapeHtml(content);
            }
        } else {
            if (rawContent.length > 100) {
                content = escapeHtml(rawContent.substring(0, 100)) + '...';
            } else {
                content = escapeHtml(rawContent);
            }
        }
        var categoryName = escapeHtml(kp.category_name || '未分类');
        var catIndex = (kp.category_index !== undefined ? kp.category_index : index) % 8;
        var time = formatTime(kp.created_at || kp.updated_at || '');
        var isSelected = selectedIds[kp.id] ? ' selected' : '';

        // 标签列表
        var tagsHtml = '';
        var tags = kp.tags || [];
        if (tags.length > 0) {
            tagsHtml = '<div class="card-tags">';
            for (var t = 0; t < tags.length; t++) {
                var tag = tags[t];
                var shape = tag.shape || 'ellipse';
                var borderRadius = shape === 'ellipse' ? '12px' : '2px';
                var color = tag.color || getTagColor(tag.name);
                tagsHtml += '<span class="card-tag" style="background:' + color + '33;color:' + color + ';border:1px solid ' + color + ';border-radius:' + borderRadius + '">' + escapeHtml(tag.name) + '</span>';
            }
            tagsHtml += '</div>';
        }

        return '<div class="knowledge-card' + isSelected + '" data-id="' + kp.id + '">' +
            '<div class="card-header">' +
                '<span class="card-title" title="' + escapeHtml(kp.title || '') + '">' + title + '</span>' +
                '<span class="card-category cat-' + catIndex + '">' + categoryName + '</span>' +
            '</div>' +
            '<div class="card-content">' + content + '</div>' +
            tagsHtml +
            '<div class="card-footer">' +
                '<div class="card-time">' + time + '</div>' +
                '<div class="card-actions">' +
                    '<button class="btn btn-edit btn-card-edit" data-id="' + kp.id + '">修改</button>' +
                    '<button class="btn btn-duplicate btn-card-duplicate" data-id="' + kp.id + '">复制</button>' +
                    '<button class="btn btn-danger btn-card-delete" data-id="' + kp.id + '">删除</button>' +
                '</div>' +
            '</div>' +
            '</div>';
    }

    function bindCardEvents() {
        var cards = document.querySelectorAll('.knowledge-card');
        for (var i = 0; i < cards.length; i++) {
            cards[i].addEventListener('click', function(e) {
                // 如果点击的是按钮，不触发卡片点击
                if (e.target.closest('button')) return;
                var id = parseInt(this.getAttribute('data-id'), 10);
                showDetailModal(id);
            });
            // Make cards draggable
            cards[i].setAttribute('draggable', 'true');
            cards[i].addEventListener('dragstart', function(e) {
                var id = parseInt(this.getAttribute('data-id'), 10);
                e.dataTransfer.setData('text/plain', id);
                e.dataTransfer.effectAllowed = 'move';
                this.style.opacity = '0.5';
                // 防止与框选拖拽冲突
                isDragging = false;
            });
            cards[i].addEventListener('dragend', function() {
                this.style.opacity = '1';
            });
        }

        // 编辑按钮
        var editBtns = document.querySelectorAll('.btn-card-edit');
        for (var j = 0; j < editBtns.length; j++) {
            editBtns[j].addEventListener('click', function(e) {
                e.stopPropagation();
                var id = parseInt(this.getAttribute('data-id'), 10);
                showEditModal(id);
            });
        }

        // 复制按钮（复制内容到剪贴板）
        var dupBtns = document.querySelectorAll('.btn-card-duplicate');
        for (var k = 0; k < dupBtns.length; k++) {
            dupBtns[k].addEventListener('click', function(e) {
                e.stopPropagation();
                e.preventDefault();
                var id = parseInt(this.getAttribute('data-id'), 10);
                copyContent(id);
            });
        }

        // 删除按钮
        var delBtns = document.querySelectorAll('.btn-card-delete');
        for (var m = 0; m < delBtns.length; m++) {
            delBtns[m].addEventListener('click', function(e) {
                e.stopPropagation();
                var id = parseInt(this.getAttribute('data-id'), 10);
                showConfirm('确定要删除该知识点吗？', function(ok) {
                    if (!ok) return;
                    API.deleteKnowledge(id).then(function() {
                        delete selectedIds[id];
                        loadKnowledgeList();
                        loadCategories();
                    }).catch(function(err) {
                        console.error('删除失败:', err);
                        showToast('删除失败，请重试', 'error');
                    });
                });
            });
        }
    }

    // ==================== 新增/编辑知识点 ====================
    function showAddModal() {
        document.getElementById('editKnowledgeId').value = '';
        document.getElementById('modalTitle').textContent = '新增知识点';
        document.getElementById('knowledgeTitle').value = '';
        document.getElementById('knowledgeContent').value = '';
        document.getElementById('knowledgeContent').style.display = 'block';
        document.getElementById('mdPreview').style.display = 'none';
        document.getElementById('btnPreviewMD').textContent = '预览';

        var select = document.getElementById('knowledgeCategory');
        select.innerHTML = '<option value="">请选择分类</option>';
        for (var i = 0; i < categories.length; i++) {
            select.innerHTML += '<option value="' + categories[i].id + '">' + escapeHtml(categories[i].name) + '</option>';
        }

        renderTagCheckboxes();
        setCheckedTagIds([]);

        document.getElementById('modalOverlay').classList.add('show');
    }

    function showEditModal(kpId) {
        var kp = null;
        for (var i = 0; i < currentKnowledgeItems.length; i++) {
            if (currentKnowledgeItems[i].id === kpId) {
                kp = currentKnowledgeItems[i];
                break;
            }
        }
        if (!kp) {
            API.getKnowledge(kpId).then(function(data) {
                fillEditModal(data);
            }).catch(function(err) {
                console.error('获取知识点失败:', err);
                showToast('获取知识点失败', 'error');
            });
            return;
        }
        fillEditModal(kp);
    }

    function fillEditModal(kp) {
        document.getElementById('editKnowledgeId').value = kp.id;
        document.getElementById('modalTitle').textContent = '编辑知识点';
        document.getElementById('knowledgeTitle').value = kp.title || '';
        document.getElementById('knowledgeContent').value = kp.content || '';
        document.getElementById('knowledgeContent').style.display = 'block';
        document.getElementById('mdPreview').style.display = 'none';
        document.getElementById('btnPreviewMD').textContent = '预览';

        var select = document.getElementById('knowledgeCategory');
        select.innerHTML = '<option value="">请选择分类</option>';
        for (var i = 0; i < categories.length; i++) {
            var selected = (categories[i].id === kp.category_id) ? ' selected' : '';
            select.innerHTML += '<option value="' + categories[i].id + '"' + selected + '>' + escapeHtml(categories[i].name) + '</option>';
        }

        renderTagCheckboxes();
        // 设置已关联的标签
        var existingTagIds = [];
        var tags = kp.tags || [];
        for (var t = 0; t < tags.length; t++) {
            existingTagIds.push(tags[t].id);
        }
        setCheckedTagIds(existingTagIds);

        document.getElementById('modalOverlay').classList.add('show');
    }

    function closeModal() {
        document.getElementById('modalOverlay').classList.remove('show');
    }

    function submitKnowledge() {
        var editId = document.getElementById('editKnowledgeId').value;
        var title = document.getElementById('knowledgeTitle').value.trim();
        var categoryId = document.getElementById('knowledgeCategory').value;
        var content = document.getElementById('knowledgeContent').value.trim();
        var tagIds = getCheckedTagIds();

        if (!title) { showToast('请输入标题', 'warning'); return; }
        if (!content) { showToast('请输入内容', 'warning'); return; }
        if (!categoryId) { showToast('请选择分类', 'warning'); return; }

        var data = {
            title: title,
            category_id: parseInt(categoryId, 10),
            content: content,
            tag_ids: tagIds
        };

        var promise;
        if (editId) {
            promise = API.updateKnowledge(parseInt(editId, 10), data);
        } else {
            promise = API.createKnowledge(data);
        }

        promise.then(function() {
            closeModal();
            loadKnowledgeList();
            loadCategories();
        }).catch(function(err) {
            console.error('提交失败:', err);
            showToast('提交失败: ' + (err.message || '请重试'), 'error');
        });
    }

    // ==================== 复制知识点 ====================
    function duplicateKnowledge(id) {
        API.duplicateKnowledge(id).then(function() {
            loadKnowledgeList();
            loadCategories();
        }).catch(function(err) {
            console.error('复制失败:', err);
            showToast('复制失败: ' + (err.message || '请重试'), 'error');
        });
    }

    // ==================== 复制内容到剪贴板 ====================
    function copyContent(kpId) {
        var content = '';
        for (var i = 0; i < currentKnowledgeItems.length; i++) {
            if (currentKnowledgeItems[i].id === kpId) {
                content = currentKnowledgeItems[i].content || '';
                break;
            }
        }
        if (!content) {
            showToast('没有可复制的内容', 'warning');
            return;
        }
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(content).then(function() {
                showToast('内容已复制到剪贴板', 'success');
            }).catch(function() {
                showToast('复制失败', 'error');
            });
        } else {
            // 降级方案
            var textarea = document.createElement('textarea');
            textarea.value = content;
            textarea.style.position = 'fixed';
            textarea.style.opacity = '0';
            document.body.appendChild(textarea);
            textarea.select();
            try {
                document.execCommand('copy');
                showToast('内容已复制到剪贴板', 'success');
            } catch (e) {
                showToast('复制失败', 'error');
            }
            document.body.removeChild(textarea);
        }
    }

    // ==================== 批量选择 ====================
    function toggleCardSelection(id) {
        if (selectedIds[id]) {
            delete selectedIds[id];
        } else {
            selectedIds[id] = true;
        }
        updateCardUI();
        updateBatchToolbar();
    }

    function selectAll() {
        var cards = document.querySelectorAll('.knowledge-card');
        for (var i = 0; i < cards.length; i++) {
            var id = parseInt(cards[i].getAttribute('data-id'), 10);
            selectedIds[id] = true;
        }
        updateCardUI();
        updateBatchToolbar();
    }

    function invertSelection() {
        var cards = document.querySelectorAll('.knowledge-card');
        for (var i = 0; i < cards.length; i++) {
            var id = parseInt(cards[i].getAttribute('data-id'), 10);
            if (selectedIds[id]) {
                delete selectedIds[id];
            } else {
                selectedIds[id] = true;
            }
        }
        updateCardUI();
        updateBatchToolbar();
    }

    function clearSelection() {
        selectedIds = {};
        updateCardUI();
        updateBatchToolbar();
    }

    function updateCardUI() {
        var cards = document.querySelectorAll('.knowledge-card');
        for (var i = 0; i < cards.length; i++) {
            var id = parseInt(cards[i].getAttribute('data-id'), 10);
            if (selectedIds[id]) {
                cards[i].classList.add('selected');
            } else {
                cards[i].classList.remove('selected');
            }
        }
    }

    function updateBatchToolbar() {
        var toolbar = document.getElementById('batchToolbar');
        var countEl = document.getElementById('batchCount');
        var exportBtn = document.getElementById('exportBtn');
        var count = Object.keys(selectedIds).length;

        if (count > 0) {
            toolbar.classList.add('show');
            countEl.textContent = '已选 ' + count + ' 个';
            exportBtn.disabled = false;
        } else {
            toolbar.classList.remove('show');
            countEl.textContent = '已选 0 个';
            exportBtn.disabled = true;
        }
    }

    function getSelectedIds() {
        var ids = [];
        for (var id in selectedIds) {
            if (selectedIds.hasOwnProperty(id)) {
                ids.push(parseInt(id, 10));
            }
        }
        return ids;
    }

    // ==================== 拖拽选择 ====================
    function onDragStart(e) {
        // 只在知识点列表区域生效，排除按钮点击
        if (e.target.closest('button')) return;
        if (e.target.closest('.empty-state')) return;
        if (!e.target.closest('.knowledge-list')) return;

        // 阻止浏览器默认文本选择行为
        e.preventDefault();

        isDragging = true;
        dragStartX = e.clientX;
        dragStartY = e.clientY;

        var box = document.getElementById('selectionBox');
        box.style.left = dragStartX + 'px';
        box.style.top = dragStartY + 'px';
        box.style.width = '0px';
        box.style.height = '0px';
        box.classList.add('show');
    }

    function onDragMove(e) {
        if (!isDragging) return;

        var currentX = e.clientX;
        var currentY = e.clientY;

        var left = Math.min(dragStartX, currentX);
        var top = Math.min(dragStartY, currentY);
        var width = Math.abs(currentX - dragStartX);
        var height = Math.abs(currentY - dragStartY);

        var box = document.getElementById('selectionBox');
        box.style.left = left + 'px';
        box.style.top = top + 'px';
        box.style.width = width + 'px';
        box.style.height = height + 'px';
    }

    function onDragEnd(e) {
        if (!isDragging) return;

        var box = document.getElementById('selectionBox');
        box.classList.remove('show');

        var currentX = e.clientX;
        var currentY = e.clientY;

        // 如果移动距离太小，视为点击
        if (Math.abs(currentX - dragStartX) < 5 && Math.abs(currentY - dragStartY) < 5) {
            isDragging = false;
            return;
        }

        var selRect = {
            left: Math.min(dragStartX, currentX),
            top: Math.min(dragStartY, currentY),
            right: Math.max(dragStartX, currentX),
            bottom: Math.max(dragStartY, currentY)
        };

        var cards = document.querySelectorAll('.knowledge-card');
        for (var i = 0; i < cards.length; i++) {
            var cardRect = cards[i].getBoundingClientRect();
            // 判断卡片是否与选择框相交
            if (!(cardRect.right < selRect.left ||
                  cardRect.left > selRect.right ||
                  cardRect.bottom < selRect.top ||
                  cardRect.top > selRect.bottom)) {
                var id = parseInt(cards[i].getAttribute('data-id'), 10);
                if (selectedIds[id]) {
                    delete selectedIds[id];
                } else {
                    selectedIds[id] = true;
                }
            }
        }

        updateCardUI();
        updateBatchToolbar();
        isDragging = false;
    }

    // ==================== 导入 ====================
    function showImportModal() {
        importData = null;
        document.getElementById('importPreview').value = '';
        document.getElementById('importPasteArea').value = '';
        document.getElementById('btnConfirmImport').disabled = true;
        document.getElementById('importFileInput').value = '';

        // 动态生成 AI 提示词模板
        var promptText = '请将以下知识点整理为 JSON 格式，每条知识点包含 title（标题）、content（内容）、category（分类名称）、tags（标签名称列表）。\n\n';
        promptText += '输出格式示例：\n```json\n[\n  {\n    "title": "知识点标题",\n    "content": "知识点的详细内容...",\n    "category": "分类名称",\n    "tags": ["标签1", "标签2"]\n  }\n]\n```\n\n';
        promptText += '可用的分类名称：\n';
        var catNames = [];
        for (var i = 0; i < categories.length; i++) { catNames.push(categories[i].name); }
        promptText += catNames.join(', ') + '\n\n';
        promptText += '可用的标签名称：\n';
        var tagNames = [];
        for (var j = 0; j < allTags.length; j++) { tagNames.push(allTags[j].name); }
        promptText += tagNames.length > 0 ? tagNames.join(', ') : '(暂无标签)';
        promptText += '\n\n注意：\n1. category 必须是上述可用分类之一，如果不存在请使用"未分类"\n2. tags 是字符串数组，标签名称尽量简短（2-6个字）\n3. 请确保输出是有效的 JSON 数组';

        document.getElementById('promptTemplate').textContent = promptText;
        document.getElementById('importModalOverlay').classList.add('show');
    }

    function closeImportModal() {
        document.getElementById('importModalOverlay').classList.remove('show');
    }

    function handleFile(file) {
        if (!file.name.endsWith('.json')) {
            showToast('请选择 JSON 文件', 'warning');
            return;
        }

        var reader = new FileReader();
        reader.onload = function(e) {
            try {
                var data = JSON.parse(e.target.result);
                importData = data;
                document.getElementById('importPreview').value = JSON.stringify(data, null, 2);
                document.getElementById('btnConfirmImport').disabled = false;
            } catch (err) {
                showToast('JSON 解析失败: ' + err.message, 'error');
                document.getElementById('importPreview').value = '';
                document.getElementById('btnConfirmImport').disabled = true;
            }
        };
        reader.readAsText(file);
    }

    function confirmImport() {
        if (!importData) {
            showToast('请先选择文件', 'warning');
            return;
        }

        API.importKnowledge(importData).then(function(result) {
            closeImportModal();
            loadKnowledgeList();
            loadCategories();
            showToast('导入成功', 'success');
        }).catch(function(err) {
            console.error('导入失败:', err);
            showToast('导入失败: ' + (err.message || '请重试'), 'error');
        });
    }

    function copyPrompt() {
        var text = document.getElementById('promptTemplate').textContent;
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).then(function() {
                var btn = document.getElementById('btnCopyPrompt');
                btn.textContent = '已复制';
                setTimeout(function() { btn.textContent = '复制'; }, 1500);
            }).catch(function() {
                fallbackCopy(text);
            });
        } else {
            fallbackCopy(text);
        }
    }

    function fallbackCopy(text) {
        var textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.select();
        try {
            document.execCommand('copy');
            var btn = document.getElementById('btnCopyPrompt');
            btn.textContent = '已复制';
            setTimeout(function() { btn.textContent = '复制'; }, 1500);
        } catch (e) {
            showToast('复制失败，请手动选择复制', 'error');
        }
        document.body.removeChild(textarea);
    }

    // ==================== 批量删除 ====================
    function deleteSelected() {
        var ids = getSelectedIds();
        if (ids.length === 0) {
            showToast('请先选择知识点', 'warning');
            return;
        }
        showConfirm('确定要删除选中的 ' + ids.length + ' 个知识点吗？', function(ok) {
            if (!ok) return;
            var promises = [];
            for (var i = 0; i < ids.length; i++) {
                promises.push(API.deleteKnowledge(ids[i]));
            }
            Promise.all(promises).then(function() {
                clearSelection();
                loadKnowledgeList();
                loadCategories();
                showToast('已删除 ' + ids.length + ' 个知识点', 'success');
            }).catch(function(err) {
                console.error('批量删除失败:', err);
                showToast('批量删除失败: ' + (err.message || '请重试'), 'error');
                loadKnowledgeList();
            });
        });
    }

    // ==================== 导出 ====================
    function showExportModal() {
        var ids = getSelectedIds();
        if (ids.length === 0) {
            showToast('请先选择知识点', 'warning');
            return;
        }
        document.getElementById('exportModalOverlay').classList.add('show');
    }

    function closeExportModal() {
        document.getElementById('exportModalOverlay').classList.remove('show');
    }

    function confirmExport() {
        var fields = {
            title: document.getElementById('exportFieldTitle').checked,
            content: document.getElementById('exportFieldContent').checked,
            category: document.getElementById('exportFieldCategory').checked,
            tags: document.getElementById('exportFieldTags').checked
        };
        closeExportModal();
        exportSelected('txt', fields);
    }

    function exportSelected(format, fields) {
        var ids = getSelectedIds();
        if (ids.length === 0) {
            showToast('请先选择知识点', 'warning');
            return;
        }
        var body = { ids: ids, format: format };
        if (fields) {
            body.fields = fields;
        }
        API.exportKnowledge(body).then(function(data) {
            var content = data.content;
            var mimeType = format === 'txt' ? 'text/plain' : 'application/json';
            var blob = new Blob([content], { type: mimeType });
            var url = URL.createObjectURL(blob);
            var a = document.createElement('a');
            a.href = url;
            a.download = data.filename || ('knowledge_export.' + format);
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            showToast('导出成功', 'success');
        }).catch(function(err) {
            console.error('导出失败:', err);
            showToast('导出失败: ' + (err.message || '请重试'), 'error');
        });
    }

    // ==================== 详情弹窗 ====================
    function showDetailModal(kpId) {
        var kp = null;
        for (var i = 0; i < currentKnowledgeItems.length; i++) {
            if (currentKnowledgeItems[i].id === kpId) {
                kp = currentKnowledgeItems[i];
                break;
            }
        }
        if (!kp) return;

        document.getElementById('detailTitle').textContent = kp.title || '无标题';
        document.getElementById('detailCategory').textContent = kp.category_name || '未分类';
        document.getElementById('detailTime').textContent = formatTime(kp.created_at || kp.updated_at || '');

        // 标签
        var tagsHtml = '';
        var tags = kp.tags || [];
        if (tags.length > 0) {
            for (var t = 0; t < tags.length; t++) {
                var tag = tags[t];
                var shape = tag.shape || 'ellipse';
                var borderRadius = shape === 'ellipse' ? '12px' : '2px';
                var color = tag.color || getTagColor(tag.name);
                tagsHtml += '<span class="card-tag" style="background:' + color + '33;color:' + color + ';border:1px solid ' + color + ';border-radius:' + borderRadius + '">' + escapeHtml(tag.name) + '</span>';
            }
        }
        document.getElementById('detailTags').innerHTML = tagsHtml;

        // 渲染 Markdown 内容
        var content = kp.content || '';
        var contentEl = document.getElementById('detailContent');
        renderMarkdownTo(contentEl, content);

        document.getElementById('detailModalOverlay').classList.add('show');
    }

    function closeDetailModal() {
        document.getElementById('detailModalOverlay').classList.remove('show');
    }

    return { init: init, loadKnowledgeList: loadKnowledgeList, loadCategories: loadCategories, loadTags: loadTags };
})();

document.addEventListener('DOMContentLoaded', App.init);

// ==================== 操作历史 ====================
function showHistoryModal() {
    document.getElementById('historyModalOverlay').classList.add('show');
    API.getOperations().then(function(ops) {
        var html = '';
        if (ops.length === 0) {
            html = '<div class="empty-state">暂无操作记录</div>';
        } else {
            html = '<table class="history-table"><thead><tr><th>时间</th><th>操作</th><th>类型</th><th>详情</th><th>操作</th></tr></thead><tbody>';
            for (var i = 0; i < ops.length; i++) {
                var op = ops[i];
                var labels = {
                    'create': '新增', 'update': '修改', 'delete': '删除',
                    'batch_delete': '批量删除', 'import': '导入'
                };
                var entityLabels = {
                    'knowledge': '知识点', 'category': '分类', 'tag': '标签'
                };
                var detail = generateOperationDetail(op);
                html += '<tr>' +
                    '<td>' + (op.created_at || '') + '</td>' +
                    '<td>' + (labels[op.op_type] || op.op_type) + '</td>' +
                    '<td>' + (entityLabels[op.entity_type] || op.entity_type) + '</td>' +
                    '<td>' + detail + '</td>' +
                    '<td><button class="btn btn-small btn-undo" data-op-id="' + op.id + '">撤销</button> <button class="btn btn-small btn-cascade-undo" data-op-id="' + op.id + '">级联撤销</button></td>' +
                    '</tr>';
            }
            html += '</tbody></table>';
        }
        document.getElementById('historyList').innerHTML = html;
        bindUndoButtons();
    });
}

function generateOperationDetail(op) {
    var entityLabel = {'knowledge': '知识点', 'category': '分类', 'tag': '标签'}[op.entity_type] || op.entity_type;
    var name = op.entity_name || '';
    var nameStr = name ? '「' + escapeHtml(name) + '」' : '';

    if (op.op_type === 'create') {
        return '新增' + entityLabel + nameStr;
    } else if (op.op_type === 'delete') {
        return '删除' + entityLabel + nameStr;
    } else if (op.op_type === 'update') {
        var before = op.before_state || {};
        var after = op.after_state || {};
        var changes = [];
        if (before.title !== after.title) {
            changes.push('标题');
        }
        if (before.content !== after.content) {
            changes.push('内容');
        }
        if (before.category_id !== after.category_id) {
            changes.push('分类');
        }
        if (changes.length > 0) {
            return '修改' + entityLabel + nameStr + '的' + changes.join('、');
        }
        return '修改' + entityLabel + nameStr;
    } else if (op.op_type === 'batch_delete') {
        var affected = op.affected_ids || [];
        var count = affected.length;
        var names = [];
        for (var i = 0; i < Math.min(affected.length, 3); i++) {
            var item = affected[i];
            if (item && item.before_state && item.before_state.title) {
                names.push('「' + escapeHtml(item.before_state.title) + '」');
            }
        }
        var nameList = names.join('、');
        if (affected.length > 3) nameList += '等';
        return '批量删除' + count + '个' + entityLabel + '：' + nameList;
    } else if (op.op_type === 'import') {
        var affected = op.affected_ids || [];
        return '导入' + affected.length + '个' + entityLabel;
    }
    return (op.op_type || '') + ' ' + entityLabel + nameStr;
}

function bindUndoButtons() {
    var btns = document.querySelectorAll('.btn-undo');
    for (var i = 0; i < btns.length; i++) {
        btns[i].addEventListener('click', function() {
            var id = parseInt(this.getAttribute('data-op-id'), 10);
            showConfirmGlobal('确定要撤销此操作吗？', function(ok) {
                if (!ok) return;
                API.undoOperation(id).then(function() {
                    showToastGlobal('撤销成功', 'success');
                    showHistoryModal();
                    App.loadKnowledgeList();
                    App.loadCategories();
                    App.loadTags();
                }).catch(function(err) {
                    showToastGlobal('撤销失败: ' + (err.message || '请重试'), 'error');
                });
            });
        });
    }
    var cascadeBtns = document.querySelectorAll('.btn-cascade-undo');
    for (var j = 0; j < cascadeBtns.length; j++) {
        cascadeBtns[j].addEventListener('click', function() {
            var id = parseInt(this.getAttribute('data-op-id'), 10);
            showConfirmGlobal('确定要级联撤销该操作及之后的所有操作吗？此操作不可逆。', function(ok) {
                if (!ok) return;
                API.undoAllOperations(id).then(function() {
                    showToastGlobal('级联撤销成功', 'success');
                    showHistoryModal();
                    App.loadKnowledgeList();
                    App.loadCategories();
                    App.loadTags();
                }).catch(function(err) {
                    showToastGlobal('级联撤销失败: ' + (err.message || '请重试'), 'error');
                });
            });
        });
    }
}

function showBackupModal() {
    document.getElementById('backupModalOverlay').classList.add('show');
    loadBackups();
}

function loadBackups() {
    API.getBackups().then(function(backups) {
        var html = '';
        if (backups.length === 0) {
            html = '<div class="empty-state">暂无备份</div>';
        } else {
            for (var i = 0; i < backups.length; i++) {
                var b = backups[i];
                var sizeKB = (b.size / 1024).toFixed(1);
                var noteHtml = b.note ? '<span class="backup-note" style="color:#e67e22;font-size:11px;">备注: ' + escapeHtml(b.note) + '</span>' : '';
                html += '<div class="backup-item">' +
                    '<div class="backup-info">' +
                        '<span class="backup-name">' + escapeHtml(b.filename) + '</span>' +
                        '<span class="backup-meta">' + b.created_at + ' | ' + sizeKB + ' KB</span>' +
                        noteHtml +
                    '</div>' +
                    '<div class="backup-actions">' +
                        '<button class="btn btn-small btn-restore" data-filename="' + escapeHtml(b.filename) + '">恢复</button>' +
                        '<button class="btn btn-small btn-danger btn-del-backup" data-filename="' + escapeHtml(b.filename) + '">删除</button>' +
                    '</div>' +
                    '</div>';
            }
        }
        document.getElementById('backupList').innerHTML = html;
        bindBackupButtons();
    });
}

function bindBackupButtons() {
    var restoreBtns = document.querySelectorAll('.btn-restore');
    for (var i = 0; i < restoreBtns.length; i++) {
        restoreBtns[i].addEventListener('click', function() {
            var fn = this.getAttribute('data-filename');
            showConfirmGlobal('恢复备份将覆盖当前数据，确定继续？', function(ok) {
                if (!ok) return;
                API.restoreBackup(fn).then(function(data) {
                    var restart = (data && data.restart);
                    if (restart) {
                        showToastGlobal('恢复成功，即将重启', 'success');
                        setTimeout(function() { location.reload(); }, 1500);
                    } else {
                        showToastGlobal('恢复成功，请刷新页面', 'success');
                        setTimeout(function() { location.reload(); }, 1500);
                    }
                }).catch(function(err) {
                    showToastGlobal('恢复失败: ' + (err.message || '请重试'), 'error');
                });
            });
        });
    }
    var delBtns = document.querySelectorAll('.btn-del-backup');
    for (var j = 0; j < delBtns.length; j++) {
        delBtns[j].addEventListener('click', function() {
            var fn = this.getAttribute('data-filename');
            showConfirmGlobal('确定删除此备份？', function(ok) {
                if (!ok) return;
                API.deleteBackup(fn).then(function() {
                    showToastGlobal('备份已删除', 'success');
                    loadBackups();
                }).catch(function(err) {
                    showToastGlobal('删除失败: ' + (err.message || '请重试'), 'error');
                });
            });
        });
    }
}

// ==================== 日志查看 ====================
function showLogModal() {
    document.getElementById('logModalOverlay').classList.add('show');
    loadLogFiles();
}

function loadLogFiles() {
    fetch('/api/logs').then(function(res) {
        return res.json();
    }).then(function(data) {
        var files = data.data || [];
        var html = '';
        for (var i = 0; i < files.length; i++) {
            var f = files[i];
            var sizeKB = (f.size / 1024).toFixed(1);
            var modified = new Date(f.modified * 1000).toLocaleString();
            html += '<div class="log-file-item' + (i === 0 ? ' active' : '') + '" data-filename="' + escapeHtml(f.name) + '">' +
                '<span class="log-file-name">' + escapeHtml(f.name) + '</span>' +
                '<span class="log-file-meta">' + modified + ' | ' + sizeKB + ' KB</span>' +
            '</div>';
        }
        document.getElementById('logFileList').innerHTML = html || '<div class="empty-state">暂无日志</div>';

        // 绑定点击事件
        var items = document.querySelectorAll('.log-file-item');
        for (var j = 0; j < items.length; j++) {
            items[j].addEventListener('click', function() {
                var allItems = document.querySelectorAll('.log-file-item');
                for (var k = 0; k < allItems.length; k++) {
                    allItems[k].classList.remove('active');
                }
                this.classList.add('active');
                loadLogContent(this.getAttribute('data-filename'));
            });
        }

        // 自动加载第一个日志
        if (files.length > 0) {
            loadLogContent(files[0].name);
        }
    });
}

function loadLogContent(filename) {
    document.getElementById('logContent').textContent = '加载中...';
    fetch('/api/logs/' + encodeURIComponent(filename) + '?lines=500').then(function(res) {
        return res.json();
    }).then(function(data) {
        var content = data.data.content || '';
        var lines = content.split('\n');
        var html = '';
        for (var i = 0; i < lines.length; i++) {
            var line = escapeHtml(lines[i]);
            if (line.indexOf('[ERROR]') !== -1) {
                html += '<span class="log-error">' + line + '</span>\n';
            } else if (line.indexOf('[WARNING]') !== -1) {
                html += '<span class="log-warning">' + line + '</span>\n';
            } else {
                html += line + '\n';
            }
        }
        document.getElementById('logContent').innerHTML = html;
    }).catch(function() {
        document.getElementById('logContent').textContent = '加载失败';
    });
}

// 全局工具函数（供模态框使用）
function escapeHtml(str) {
    if (!str) return '';
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
}

// ==================== 设置 ====================
var _settingsConfig = null;

function showSettingsModal() {
    API.getConfig().then(function(config) {
        _settingsConfig = config;
        // 登录验证
        var disableLogin = document.getElementById('settingsDisableLogin');
        disableLogin.value = config.disable_login ? 'true' : 'false';
        // 密码方式单选
        var radioFixed = document.querySelector('input[name="passwordMode"][value="fixed"]');
        var radioTemp = document.querySelector('input[name="passwordMode"][value="temp"]');
        if (config.enable_temp_password) {
            radioTemp.checked = true;
        } else {
            radioFixed.checked = true;
        }
        // 密码输入框
        var pwdField = document.getElementById('settingsPassword');
        pwdField.value = '';
        var statusEl = document.getElementById('passwordStatus');
        if (config.has_password) {
            pwdField.placeholder = '输入新密码以修改';
            statusEl.textContent = '已设置密码';
            statusEl.style.color = '#27ae60';
        } else {
            pwdField.placeholder = '请输入密码';
            statusEl.textContent = '未设置密码';
            statusEl.style.color = '#999';
        }
        // 其他设置
        document.getElementById('settingsBackup').value = config.enable_startup_backup ? 'true' : 'false';
        document.getElementById('settingsDebug').value = config.debug ? 'true' : 'false';
        // 联动
        updateLoginSubOptions();
        updatePasswordMode();
        document.getElementById('settingsModalOverlay').classList.add('show');
    }).catch(function(err) {
        showToastGlobal('加载配置失败: ' + (err.message || '请重试'), 'error');
    });
}

function updateLoginSubOptions() {
    var disableLogin = document.getElementById('settingsDisableLogin').value === 'true';
    document.getElementById('loginSubOptions').style.display = disableLogin ? 'none' : '';
}

function updatePasswordMode() {
    var radioTemp = document.querySelector('input[name="passwordMode"][value="temp"]');
    var isTemp = radioTemp.checked;
    document.getElementById('fixedPasswordGroup').style.display = isTemp ? 'none' : '';
    document.getElementById('tempPasswordHint').style.display = isTemp ? '' : 'none';
}

function closeSettingsModal() {
    document.getElementById('settingsModalOverlay').classList.remove('show');
}

function saveSettings() {
    var disableLogin = document.getElementById('settingsDisableLogin').value === 'true';
    var radioTemp = document.querySelector('input[name="passwordMode"][value="temp"]');
    var enableTempPassword = !disableLogin && radioTemp.checked;

    var data = {
        enable_startup_backup: document.getElementById('settingsBackup').value === 'true',
        debug: document.getElementById('settingsDebug').value === 'true',
        disable_login: disableLogin,
        enable_temp_password: enableTempPassword
    };

    // 固定密码模式且输入了密码
    if (!disableLogin && !enableTempPassword && document.getElementById('settingsPassword').value) {
        data.password = document.getElementById('settingsPassword').value;
    }

    API.saveConfig(data).then(function() {
        showToastGlobal('设置已保存', 'success');
        closeSettingsModal();
        // 如果修改了密码，跳转到登录页重新登录
        if (data.password) {
            setTimeout(function() {
                window.location.href = '/login';
            }, 1000);
        }
    }).catch(function(err) {
        showToastGlobal('保存失败: ' + (err.message || '请重试'), 'error');
    });
}

var resetTimer = null;
var cacheTimer = null;
var restartTimer = null;

function showLoadingOverlay() {
    var el = document.getElementById('loadingOverlay');
    if (el) el.classList.add('show');
}

function hideLoadingOverlay() {
    var el = document.getElementById('loadingOverlay');
    if (el) el.classList.remove('show');
}

function startCountdown(btnId, spanId, timerVar) {
    var countdown = 3;
    var btn = document.getElementById(btnId);
    var span = document.getElementById(spanId);
    btn.disabled = true;
    span.textContent = countdown;

    var timer = setInterval(function() {
        countdown--;
        if (countdown <= 0) {
            clearInterval(timer);
            if (timerVar === 'reset') resetTimer = null;
            else if (timerVar === 'cache') cacheTimer = null;
            else restartTimer = null;
            btn.disabled = false;
            btn.textContent = btnId === 'resetConfirmBtn' ? '确认重置' : (btnId === 'restartConfirmBtn' ? '确认重启' : '确认清除');
        } else {
            span.textContent = countdown;
        }
    }, 1000);

    if (timerVar === 'reset') resetTimer = timer;
    else if (timerVar === 'cache') cacheTimer = timer;
    else restartTimer = timer;
}

function stopTimer(timerVar) {
    var timer = timerVar === 'reset' ? resetTimer : (timerVar === 'cache' ? cacheTimer : restartTimer);
    if (timer) {
        clearInterval(timer);
        if (timerVar === 'reset') resetTimer = null;
        else if (timerVar === 'cache') cacheTimer = null;
        else restartTimer = null;
    }
}

// ====== 清除缓存 ======
function showCacheModal() {
    closeSettingsModal();
    document.getElementById('cacheModalOverlay').classList.add('show');
    startCountdown('cacheConfirmBtn', 'cacheCountdown', 'cache');
}

function closeCacheModal() {
    stopTimer('cache');
    document.getElementById('cacheModalOverlay').classList.remove('show');
}

function clearCache() {
    var btn = document.getElementById('cacheConfirmBtn');
    btn.disabled = true;
    btn.textContent = '清除中...';
    showLoadingOverlay();
    API.clearCache().then(function(res) {
        // 保存重启令牌，用于重启后自动登录
        if (res.restart_token) {
            localStorage.setItem('restart_token', res.restart_token);
        }
        showToastGlobal(res.message || '缓存已清除', 'success');
        closeCacheModal();
        // 轮询等待系统重启完成，然后刷新页面
        var attempts = 0;
        var poll = setInterval(function() {
            attempts++;
            fetch('/api/config').then(function(r) {
                if (r.ok) {
                    clearInterval(poll);
                    window.location.reload();
                }
            }).catch(function() {
                if (attempts >= 30) {
                    clearInterval(poll);
                    hideLoadingOverlay();
                    showToastGlobal('系统重启超时，请手动刷新页面', 'error');
                }
            });
        }, 1000);
    }).catch(function(err) {
        hideLoadingOverlay();
        showToastGlobal('清除缓存失败: ' + (err.message || '请重试'), 'error');
        btn.disabled = false;
        btn.textContent = '确认清除';
    });
}

// ====== 重启系统 ======
function showResetModal() {
    closeSettingsModal();
    document.getElementById('resetModalOverlay').classList.add('show');
    startCountdown('resetConfirmBtn', 'resetCountdown', 'reset');
}

function closeResetModal() {
    stopTimer('reset');
    document.getElementById('resetModalOverlay').classList.remove('show');
}

function resetSystem() {
    var btn = document.getElementById('resetConfirmBtn');
    btn.disabled = true;
    btn.textContent = '重置中...';
    showLoadingOverlay();
    API.resetSystem().then(function(res) {
        hideLoadingOverlay();
        showToastGlobal(res.message || '系统已重置', 'success');
        closeResetModal();
    }).catch(function(err) {
        hideLoadingOverlay();
        showToastGlobal('重置失败: ' + (err.message || '请重试'), 'error');
        btn.disabled = false;
        btn.textContent = '确认重置';
    });
}

// ====== 重启系统 ======
function showRestartModal() {
    closeSettingsModal();
    document.getElementById('restartModalOverlay').classList.add('show');
    startCountdown('restartConfirmBtn', 'restartCountdown', 'restart');
}

function closeRestartModal() {
    stopTimer('restart');
    document.getElementById('restartModalOverlay').classList.remove('show');
}

function restartSystem() {
    var btn = document.getElementById('restartConfirmBtn');
    btn.disabled = true;
    btn.textContent = '重启中...';
    showLoadingOverlay();
    API.restartSystem().then(function(res) {
        // 保存重启令牌，用于重启后自动登录
        if (res.restart_token) {
            localStorage.setItem('restart_token', res.restart_token);
        }
        showToastGlobal(res.message || '系统正在重启', 'success');
        closeRestartModal();
        // 轮询等待系统重启完成，然后刷新页面（由新服务器处理自动登录）
        var attempts = 0;
        var poll = setInterval(function() {
            attempts++;
            fetch('/api/config').then(function(r) {
                if (r.ok) {
                    clearInterval(poll);
                    window.location.reload();
                }
            }).catch(function() {
                if (attempts >= 30) {
                    clearInterval(poll);
                    hideLoadingOverlay();
                    showToastGlobal('系统重启超时，请手动刷新页面', 'error');
                }
            });
        }, 1000);
    }).catch(function(err) {
        hideLoadingOverlay();
        showToastGlobal('重启失败: ' + (err.message || '请重试'), 'error');
        btn.disabled = false;
        btn.textContent = '确认重启';
    });
}

function showToastGlobal(message, type) {
    type = type || 'success';
    var container = document.getElementById('toastContainer');
    if (!container) return;
    var toast = document.createElement('div');
    toast.className = 'toast toast-' + type;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(function() {
        toast.style.animation = 'toastFadeOut 0.3s ease forwards';
        setTimeout(function() {
            if (toast.parentNode) toast.parentNode.removeChild(toast);
        }, 300);
    }, 3000);
}

function showConfirmGlobal(message, callback) {
    document.getElementById('confirmMessage').textContent = message;
    document.getElementById('confirmModalOverlay').classList.add('show');

    var okBtn = document.getElementById('confirmOkBtn');
    var cancelBtn = document.getElementById('confirmCancelBtn');
    var cleanup = function() {
        document.getElementById('confirmModalOverlay').classList.remove('show');
        okBtn.removeEventListener('click', onOk);
        cancelBtn.removeEventListener('click', onCancel);
    };
    var onOk = function() { cleanup(); callback(true); };
    var onCancel = function() { cleanup(); callback(false); };
    okBtn.addEventListener('click', onOk);
    cancelBtn.addEventListener('click', onCancel);
}