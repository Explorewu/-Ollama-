/**
 * 群组模块
 * 群组对话相关功能
 */
(function() {
    const Group = {
        init(app) {
            this.app = app;
        },

        loadGroups() {
            const app = this.app;
            const groups = Storage.getGroups();
            const groupsList = document.getElementById('groupsList');
            if (!groupsList) return;

            groupsList.innerHTML = groups.map(group => `
                <div class="group-card ${app.state.currentGroup?.id === group.id ? 'active' : ''}" data-group-id="${group.id}">
                    <div class="group-card-header">
                        <div class="group-avatar-wrapper">${group.avatar}</div>
                        <div class="group-card-info">
                            <h4 class="group-card-name">${group.name}</h4>
                            <p class="group-card-desc">${group.description || '暂无描述'}</p>
                        </div>
                    </div>
                    <div class="group-actions">
                        <button class="group-action-btn edit-btn" data-action="edit" data-group-id="${group.id}" title="编辑">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                        </button>
                        <button class="group-action-btn delete" data-action="delete" data-group-id="${group.id}" title="删除">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                        </button>
                    </div>
                </div>
            `).join('');

            groupsList.onclick = (e) => {
                const target = e.target.closest('.group-action-btn');
                if (!target) return;

                const action = target.dataset.action;
                const groupId = target.dataset.groupId;

                if (action === 'edit') {
                    app.showGroupModal('edit', groupId);
                } else if (action === 'delete') {
                    app.showDeleteConfirm(groupId);
                }
            };

            groupsList.onmousedown = (e) => {
                const card = e.target.closest('.group-card');
                if (card && !e.target.closest('.group-action-btn')) {
                    app.selectGroup(card.dataset.groupId);
                }
            };

            this.initHideDefaultGroup();
        },

        initHideDefaultGroup() {
            const hideBtn = document.getElementById('hideDefaultGroupBtn');
            if (!hideBtn) return;

            const isHidden = localStorage.getItem('defaultGroupHidden') === 'true';
            this.updateDefaultGroupVisibility(isHidden);

            hideBtn.addEventListener('click', () => {
                const isHidden = localStorage.getItem('defaultGroupHidden') === 'true';
                const newState = !isHidden;
                localStorage.setItem('defaultGroupHidden', newState.toString());
                this.updateDefaultGroupVisibility(newState);
            });
        },

        updateDefaultGroupVisibility(hidden) {
            const hideBtn = document.getElementById('hideDefaultGroupBtn');
            const groupChatHeader = document.querySelector('.group-chat-header');

            if (hideBtn) {
                hideBtn.textContent = hidden ? '显示' : '隐藏';
            }

            if (groupChatHeader) {
                if (hidden) {
                    groupChatHeader.classList.add('header-hidden');
                } else {
                    groupChatHeader.classList.remove('header-hidden');
                }
            }
        },

        selectGroup(groupId) {
            const app = this.app;
            const groups = Storage.getGroups();
            const group = groups.find(g => g.id === groupId);

            if (!group) return;

            app.state.currentGroup = group;
            localStorage.setItem('lastSelectedGroupId', groupId);

            document.querySelectorAll('.group-card').forEach(card => {
                card.classList.toggle('active', card.dataset.groupId === groupId);
            });

            this.loadGroupConversationHistory(groupId);
        },

        showGroupModal(mode = 'create', groupId = null) {
            const app = this.app;
            let modal = document.getElementById('groupModal');
            const isEdit = mode === 'edit';

            if (!modal) {
                modal = document.createElement('div');
                modal.id = 'groupModal';
                modal.className = 'modal-overlay';
                modal.innerHTML = `
                    <div class="modal-content">
                        <div class="modal-header">
                            <h3 id="groupModalTitle">创建群组</h3>
                            <button class="modal-close" id="groupModalClose">&times;</button>
                        </div>
                        <form id="groupForm">
                            <div class="form-group">
                                <label for="groupNameInput">群组名称 *</label>
                                <input type="text" id="groupNameInput" placeholder="输入群组名称" required>
                            </div>
                            <div class="form-group">
                                <label for="groupDescInput">描述</label>
                                <textarea id="groupDescInput" placeholder="简短描述这个群组的特点" rows="2"></textarea>
                            </div>
                            <div class="form-group">
                                <label>选择角色（至少2个）</label>
                                <div id="groupPersonaSelect" class="persona-select-grid"></div>
                            </div>
                            <div class="form-group advanced-toggle">
                                <button type="button" class="toggle-btn" id="groupAdvancedToggle">高级选项 ▾</button>
                                <div class="advanced-options" id="groupAdvancedOptions" style="display: none;">
                                    <div class="form-group">
                                        <label for="groupAvatarInput">群组头像</label>
                                        <input type="text" id="groupAvatarInput" placeholder="👥" maxlength="4">
                                    </div>
                                    <div class="form-group">
                                        <label for="groupRoundInput">对话轮数</label>
                                        <select id="groupRoundInput">
                                            <option value="1">1轮（依次回复）</option>
                                            <option value="2" selected>2轮</option>
                                            <option value="3">3轮</option>
                                            <option value="5">5轮</option>
                                        </select>
                                    </div>
                                </div>
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn-secondary" id="groupModalCancel">取消</button>
                                <button type="submit" class="btn-primary">${isEdit ? '保存' : '创建'}</button>
                            </div>
                        </form>
                    </div>
                `;
                document.body.appendChild(modal);
            }

            const title = document.getElementById('groupModalTitle');
            const form = document.getElementById('groupForm');

            if (isEdit && groupId) {
                const groups = Storage.getGroups();
                const group = groups.find(g => g.id === groupId);
                if (group) {
                    title.textContent = '编辑群组';
                    document.getElementById('groupNameInput').value = group.name;
                    document.getElementById('groupDescInput').value = group.description || '';
                    document.getElementById('groupAvatarInput').value = group.avatar || '👥';
                    document.getElementById('groupRoundInput').value = group.rounds || 2;
                    app.state.editingGroupId = groupId;
                }
            } else {
                title.textContent = '创建群组';
                form.reset();
                app.state.editingGroupId = null;
            }

            this.renderGroupPersonaSelect(isEdit && groupId ? Storage.getGroups().find(g => g.id === groupId)?.personas : []);

            modal.classList.add('active');
        },

        renderGroupPersonaSelect(selectedPersonas = []) {
            const container = document.getElementById('groupPersonaSelect');
            if (!container) return;

            const personas = Storage.getPersonas();
            container.innerHTML = personas.map(p => `
                <label class="persona-checkbox ${selectedPersonas?.includes(p.id) ? 'selected' : ''}">
                    <input type="checkbox" value="${p.id}" ${selectedPersonas?.includes(p.id) ? 'checked' : ''}>
                    <span class="persona-avatar">${p.avatar}</span>
                    <span class="persona-name">${p.name}</span>
                </label>
            `).join('');

            container.querySelectorAll('input').forEach(input => {
                input.addEventListener('change', () => {
                    input.parentElement.classList.toggle('selected', input.checked);
                });
            });
        },

        saveGroup() {
            const app = this.app;
            const name = document.getElementById('groupNameInput')?.value.trim();
            const description = document.getElementById('groupDescInput')?.value.trim();
            const avatar = document.getElementById('groupAvatarInput')?.value.trim() || '👥';
            const rounds = parseInt(document.getElementById('groupRoundInput')?.value) || 2;

            const selectedPersonas = Array.from(document.querySelectorAll('#groupPersonaSelect input:checked'))
                .map(input => input.value);

            if (!name) {
                app.showToast('请输入群组名称', 'error');
                return;
            }

            if (selectedPersonas.length < 2) {
                app.showToast('请至少选择2个角色', 'error');
                return;
            }

            const groupData = {
                name,
                description,
                avatar,
                rounds,
                personas: selectedPersonas
            };

            if (app.state.editingGroupId) {
                Storage.updateGroup(app.state.editingGroupId, groupData);
                app.showToast('群组更新成功', 'success');
            } else {
                Storage.createGroup(groupData);
                app.showToast('群组创建成功', 'success');
            }

            app.hideGroupModal();
            app.loadGroups();

            const groups = Storage.getGroups();
            const newGroup = groups[groups.length - 1];
            app.selectGroup(newGroup.id);
        },

        showDeleteConfirm(groupId) {
            const app = this.app;
            app.state.deletingGroupId = groupId;

            let modal = document.getElementById('deleteConfirmModal');
            if (!modal) {
                modal = document.createElement('div');
                modal.id = 'deleteConfirmModal';
                modal.className = 'modal-overlay';
                modal.innerHTML = `
                    <div class="modal-content delete-confirm-modal">
                        <div class="modal-header">
                            <h3>确认删除</h3>
                            <button class="modal-close" id="deleteConfirmClose">&times;</button>
                        </div>
                        <div class="modal-body">
                            <p>确定要删除这个群组吗？此操作不可撤销。</p>
                        </div>
                        <div class="modal-footer">
                            <button class="btn-secondary" id="deleteConfirmCancel">取消</button>
                            <button class="btn-danger" id="deleteConfirmConfirm">删除</button>
                        </div>
                    </div>
                `;
                document.body.appendChild(modal);
            }

            modal.classList.add('active');
        },

        confirmDeleteGroup() {
            const app = this.app;
            if (!app.state.deletingGroupId) return;

            Storage.deleteGroup(app.state.deletingGroupId);

            if (app.state.currentGroup?.id === app.state.deletingGroupId) {
                app.state.currentGroup = null;
            }

            app.hideDeleteConfirm();
            app.showToast('群组已删除', 'success');
            app.loadGroups();
        },

        hideGroupModal() {
            const modal = document.getElementById('groupModal');
            if (modal) {
                modal.classList.remove('active');
            }
        },

        hideDeleteConfirm() {
            const modal = document.getElementById('deleteConfirmModal');
            if (modal) {
                modal.classList.remove('active');
            }
        },

        loadGroupConversationHistory(groupId) {
            const app = this.app;
            const group = Storage.getGroups().find(g => g.id === groupId);
            if (!group) return;

            const historyContainer = document.getElementById('groupChatHistory');
            if (!historyContainer) return;

            const history = Storage.getGroupConversation(groupId);
            historyContainer.innerHTML = '';

            if (history.length === 0) {
                historyContainer.innerHTML = '<div class="empty-state">开始群组对话吧！</div>';
                return;
            }

            history.forEach(msg => {
                app.appendGroupMessage(msg.type, msg.content, msg.persona);
            });
        },

        clearGroupChatUI() {
            const historyContainer = document.getElementById('groupChatHistory');
            if (historyContainer) {
                historyContainer.innerHTML = '<div class="empty-state">开始群组对话吧！</div>';
            }
        }
    };

    window.AppGroup = Group;
})();
