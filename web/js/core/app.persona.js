/**
 * 人设模块
 * 角色卡管理相关功能
 */
(function() {
    const Persona = {
        init(app) {
            this.app = app;
            this.initPersonaUI();
        },

        initPersonaUI() {
            this.renderPersonaGrid();
            this.updatePersonaDetail();
            this.bindPersonaEvents();
        },

        renderPersonaGrid() {
            const app = this.app;
            const grid = document.getElementById('personaGrid');
            if (!grid) return;

            const personas = Storage.getPersonas();
            const currentPersona = Storage.getCurrentPersona();

            grid.innerHTML = personas.map(persona => `
                <div class="persona-card ${persona.id === currentPersona.id ? 'active' : ''}"
                     data-persona-id="${persona.id}"
                     style="--persona-color: ${persona.color}">
                    <div class="persona-card-header">
                        <div class="persona-card-avatar">${persona.avatar}</div>
                        ${persona.isCustom ? '<span class="custom-badge">自定义</span>' : ''}
                    </div>
                    <div class="persona-card-name">${persona.name}</div>
                    <div class="persona-card-desc">${persona.description}</div>
                    <button class="persona-edit-btn" title="编辑角色">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                        </svg>
                    </button>
                </div>
            `).join('');
        },

        updatePersonaDetail() {
            const currentPersona = Storage.getCurrentPersona();

            const avatarEl = document.getElementById('currentPersonaAvatar');
            const nameEl = document.getElementById('currentPersonaName');
            const descEl = document.getElementById('personaDescription');
            const promptEl = document.getElementById('personaSystemPrompt');

            if (avatarEl) avatarEl.textContent = currentPersona.avatar;
            if (nameEl) nameEl.textContent = currentPersona.name;
            if (descEl) descEl.textContent = currentPersona.description;
            if (promptEl) promptEl.value = currentPersona.systemPrompt || '';
        },

        bindPersonaEvents() {
            const app = this.app;

            document.getElementById('personaGrid')?.addEventListener('click', (e) => {
                const card = e.target.closest('.persona-card');
                const editBtn = e.target.closest('.persona-edit-btn');

                if (editBtn && card) {
                    e.stopPropagation();
                    this.openPersonaEditor(card.dataset.personaId);
                } else if (card) {
                    Storage.setCurrentPersona(card.dataset.personaId);
                    this.renderPersonaGrid();
                    this.updatePersonaDetail();
                    app.showToast(`已切换到 ${Storage.getCurrentPersona().name}`, 'success');
                }
            });
        },

        createPersonaEditorModal() {
            const modal = document.createElement('div');
            modal.id = 'personaEditorModal';
            modal.className = 'modal-overlay';
            modal.innerHTML = `
                <div class="modal-content persona-editor-modal">
                    <div class="modal-header">
                        <h3 id="personaEditorTitle">创建新角色</h3>
                        <button class="modal-close" id="closePersonaEditor">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <line x1="18" y1="6" x2="6" y2="18"/>
                                <line x1="6" y1="6" x2="18" y2="18"/>
                            </svg>
                        </button>
                    </div>
                    <div class="modal-body">
                        <input type="hidden" id="editingPersonaId">
                        
                        <div class="form-group">
                            <label for="personaNameInput">角色名称 *</label>
                            <input type="text" id="personaNameInput" placeholder="输入角色名称" maxlength="50">
                        </div>
                        
                        <div class="form-group">
                            <label for="personaDescInput">角色描述</label>
                            <textarea id="personaDescInput" placeholder="简短描述这个角色的特点" maxlength="200" rows="2"></textarea>
                        </div>
                        
                        <div class="form-row">
                            <div class="form-group">
                                <label for="personaAvatarInput">头像</label>
                                <div class="avatar-selector">
                                    <input type="text" id="personaAvatarInput" placeholder="🤖" maxlength="4" class="avatar-input">
                                    <div class="avatar-presets" id="avatarPresets"></div>
                                </div>
                            </div>
                            
                            <div class="form-group">
                                <label for="personaColorInput">主题颜色</label>
                                <div class="color-picker-wrapper">
                                    <input type="color" id="personaColorInput" value="#059669" class="color-input">
                                    <div class="color-presets" id="colorPresets"></div>
                                </div>
                            </div>
                        </div>
                        
                        <div class="form-group">
                            <label for="personaPromptInput">系统提示词 *</label>
                            <div class="prompt-tips">
                                <span class="tip-icon">💡</span>
                                <span>提示：越详细、具体的提示词，角色表现越准确</span>
                            </div>
                            <textarea id="personaPromptInput" placeholder="定义这个AI助手的性格、行为准则，专业领域等。例如：'你是一位资深的产品经理，拥有10年互联网产品经验，擅长用户需求分析和产品规划...'" rows="6" maxlength="5000"></textarea>
                            <div class="char-counter"><span id="promptCharCount">0</span> / 5000</div>
                        </div>
                        
                        <div class="form-group">
                            <label for="personaExampleInput">对话示例（可选）</label>
                            <textarea id="personaExampleInput" placeholder="输入几个对话示例，帮助AI理解期望的回复风格。每行一个示例，格式：用户消息|AI回复" rows="3" maxlength="1000"></textarea>
                        </div>
                        
                        <div class="form-group advanced-toggle">
                            <button class="toggle-btn" id="toggleAdvancedSettings">
                                <span>高级设置</span>
                                <svg class="chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <polyline points="6 9 12 15 18 9"/>
                                </svg>
                            </button>
                            <div class="advanced-settings" id="advancedSettings" style="display: none;">
                                <div class="form-row">
                                    <div class="form-group">
                                        <label for="personaTemperature">回复温度</label>
                                        <input type="range" id="personaTemperature" min="0" max="2" step="0.1" value="0.7">
                                        <span class="range-value" id="temperatureValue">0.7</span>
                                    </div>
                                    <div class="form-group">
                                        <label for="personaMaxTokens">最大回复长度</label>
                                        <select id="personaMaxTokens">
                                            <option value="512">短 (512 tokens)</option>
                                            <option value="1024" selected>中等 (1024 tokens)</option>
                                            <option value="2048">长 (2048 tokens)</option>
                                            <option value="4096">超长 (4096 tokens)</option>
                                        </select>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button class="btn-secondary" id="cancelPersonaEdit">取消</button>
                        <button class="btn-danger" id="deletePersonaBtn" style="display: none;">删除</button>
                        <button class="btn-primary" id="savePersonaBtn">保存</button>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
            this.initPersonaEditorEvents();
        },

        initPersonaEditorEvents() {
            const app = this.app;
            const modal = document.getElementById('personaEditorModal');
            if (!modal) return;

            document.getElementById('closePersonaEditor')?.addEventListener('click', () => {
                this.closePersonaEditor();
            });

            document.getElementById('cancelPersonaEdit')?.addEventListener('click', () => {
                this.closePersonaEditor();
            });

            modal?.addEventListener('click', (e) => {
                if (e.target === modal) this.closePersonaEditor();
            });

            document.getElementById('savePersonaBtn')?.addEventListener('click', () => {
                this.savePersonaFromEditor();
            });

            document.getElementById('deletePersonaBtn')?.addEventListener('click', () => {
                this.deleteCurrentPersona();
            });

            document.getElementById('toggleAdvancedSettings')?.addEventListener('click', () => {
                const settings = document.getElementById('advancedSettings');
                const chevron = document.querySelector('#toggleAdvancedSettings .chevron');
                if (settings) {
                    const isHidden = settings.style.display === 'none';
                    settings.style.display = isHidden ? 'block' : 'none';
                    if (chevron) {
                        chevron.style.transform = isHidden ? 'rotate(180deg)' : 'rotate(0)';
                    }
                }
            });

            document.getElementById('personaTemperature')?.addEventListener('input', (e) => {
                const value = e.target.value;
                const display = document.getElementById('temperatureValue');
                if (display) display.textContent = value;
            });

            document.getElementById('personaPromptInput')?.addEventListener('input', (e) => {
                const count = document.getElementById('promptCharCount');
                if (count) count.textContent = e.target.value.length;
            });

            this.initAvatarPresets();
            this.initColorPresets();
        },

        initAvatarPresets() {
            const presets = [
                '🤖', '👨‍💻', '👩‍💻', '✍️', '📊', '👨‍🏫', '👩‍🏫', '🎨',
                '🎭', '🔬', '🚀', '💡', '🎵', '🏛️', '🧙', '🦸',
                '👩‍🔬', '👨‍🔬', '👩‍⚕️', '👨‍⚕️', '👩‍🌾', '👨‍🌾', '👩‍🍳', '👨‍🍳'
            ];
            const container = document.getElementById('avatarPresets');
            if (!container) return;

            container.innerHTML = presets.map(avatar => `
                <button class="avatar-preset" data-avatar="${avatar}">${avatar}</button>
            `).join('');

            container.addEventListener('click', (e) => {
                const btn = e.target.closest('.avatar-preset');
                if (btn) {
                    const input = document.getElementById('personaAvatarInput');
                    if (input) input.value = btn.dataset.avatar;
                }
            });
        },

        initColorPresets() {
            const colors = [
                '#059669', '#3b82f6', '#8b5cf6', '#f59e0b', '#10b981',
                '#ef4444', '#ec4899', '#6366f1', '#14b8a6', '#f97316',
                '#84cc16', '#06b6d4', '#a855f7', '#f43f5e', '#78716c'
            ];
            const container = document.getElementById('colorPresets');
            if (!container) return;

            container.innerHTML = colors.map(color => `
                <button class="color-preset" data-color="${color}" style="background-color: ${color}"></button>
            `).join('');

            container.addEventListener('click', (e) => {
                const btn = e.target.closest('.color-preset');
                if (btn) {
                    const input = document.getElementById('personaColorInput');
                    if (input) input.value = btn.dataset.color;
                }
            });
        },

        openPersonaEditor(personaId = null) {
            const app = this.app;
            if (!document.getElementById('personaEditorModal')) {
                this.createPersonaEditorModal();
            }

            const modal = document.getElementById('personaEditorModal');
            const title = document.getElementById('personaEditorTitle');
            const deleteBtn = document.getElementById('deletePersonaBtn');
            const idInput = document.getElementById('editingPersonaId');

            if (personaId) {
                const persona = Storage.getPersona(personaId);
                if (!persona) {
                    app.showToast('角色卡不存在', 'error');
                    return;
                }

                title.textContent = '编辑角色';
                deleteBtn.style.display = 'inline-flex';
                idInput.value = personaId;

                document.getElementById('personaNameInput').value = persona.name;
                document.getElementById('personaDescInput').value = persona.description || '';
                document.getElementById('personaAvatarInput').value = persona.avatar;
                document.getElementById('personaColorInput').value = persona.color;
                document.getElementById('personaPromptInput').value = persona.systemPrompt;
                document.getElementById('promptCharCount').textContent = persona.systemPrompt.length;

                if (persona.temperature) {
                    document.getElementById('personaTemperature').value = persona.temperature;
                    document.getElementById('temperatureValue').textContent = persona.temperature;
                }
                if (persona.maxTokens) {
                    document.getElementById('personaMaxTokens').value = persona.maxTokens;
                }
            } else {
                title.textContent = '创建新角色';
                deleteBtn.style.display = 'none';
                idInput.value = '';

                document.getElementById('personaNameInput').value = '';
                document.getElementById('personaDescInput').value = '';
                document.getElementById('personaAvatarInput').value = '🤖';
                document.getElementById('personaColorInput').value = Storage.getRandomColor();
                document.getElementById('personaPromptInput').value = '';
                document.getElementById('promptCharCount').textContent = '0';
                document.getElementById('personaTemperature').value = 0.7;
                document.getElementById('temperatureValue').textContent = '0.7';
                document.getElementById('personaMaxTokens').value = '1024';
            }

            modal.classList.add('active');
        },

        closePersonaEditor() {
            const modal = document.getElementById('personaEditorModal');
            if (modal) modal.classList.remove('active');
        },

        savePersonaFromEditor() {
            const app = this.app;
            const id = document.getElementById('editingPersonaId').value;
            const name = document.getElementById('personaNameInput').value.trim();
            const description = document.getElementById('personaDescInput').value.trim();
            const avatar = document.getElementById('personaAvatarInput').value.trim() || '🤖';
            const color = document.getElementById('personaColorInput').value;
            const systemPrompt = document.getElementById('personaPromptInput').value.trim();

            if (!name) {
                app.showToast('请输入角色名称', 'warning');
                return;
            }
            if (!systemPrompt) {
                app.showToast('请输入系统提示词', 'warning');
                return;
            }
            if (name.length > 50) {
                app.showToast('角色名称不能超过50个字符', 'warning');
                return;
            }
            if (systemPrompt.length > 5000) {
                app.showToast('系统提示词不能超过5000个字符', 'warning');
                return;
            }

            const personas = Storage.getPersonas();
            const duplicate = personas.find(p => 
                p.name.toLowerCase() === name.toLowerCase() && p.id !== id
            );
            if (duplicate) {
                app.showToast('角色名称已存在', 'warning');
                return;
            }

            const data = {
                name,
                description,
                avatar,
                color,
                systemPrompt,
                temperature: parseFloat(document.getElementById('personaTemperature').value),
                maxTokens: parseInt(document.getElementById('personaMaxTokens').value)
            };

            if (id) {
                const updated = Storage.updatePersona(id, data);
                if (updated) {
                    app.showToast('角色已更新', 'success');
                    this.closePersonaEditor();
                    this.renderPersonaGrid();
                    this.updatePersonaDetail();
                } else {
                    app.showToast('更新失败', 'error');
                }
            } else {
                const newPersona = Storage.addPersona(data);
                if (newPersona) {
                    app.showToast('角色已创建', 'success');
                    this.closePersonaEditor();
                    this.renderPersonaGrid();
                    Storage.setCurrentPersona(newPersona.id);
                    this.renderPersonaGrid();
                    this.updatePersonaDetail();
                } else {
                    app.showToast('创建失败', 'error');
                }
            }
        },

        deleteCurrentPersona() {
            const app = this.app;
            const id = document.getElementById('editingPersonaId').value;
            if (!id) return;

            const persona = Storage.getPersona(id);
            if (!persona) return;

            if (!confirm(`确定要删除角色"${persona.name}"吗？此操作不可恢复。`)) {
                return;
            }

            if (!persona.isCustom) {
                app.showToast('不能删除默认角色卡', 'warning');
                return;
            }

            const success = Storage.deletePersona(id);
            if (success) {
                app.showToast('角色已删除', 'success');
                this.closePersonaEditor();
                this.renderPersonaGrid();
                this.updatePersonaDetail();
            } else {
                app.showToast('删除失败', 'error');
            }
        },

        openPersonaImportDialog() {
            const app = this.app;
            const input = document.createElement('input');
            input.type = 'file';
            input.accept = '.json';
            input.style.display = 'none';

            input.addEventListener('change', (e) => {
                const file = e.target.files[0];
                if (!file) return;

                const reader = new FileReader();
                reader.onload = (event) => {
                    try {
                        const persona = JSON.parse(event.target.result);
                        if (!persona.name || !persona.systemPrompt) {
                            app.showToast('角色卡格式不正确', 'error');
                            return;
                        }

                        const imported = Storage.importPersona(JSON.stringify(persona));
                        if (imported) {
                            app.showToast(`角色"${imported.name}"导入成功`, 'success');
                            this.renderPersonaGrid();
                        } else {
                            app.showToast('导入失败', 'error');
                        }
                    } catch (error) {
                        app.showToast('解析文件失败', 'error');
                    }
                };
                reader.readAsText(file);
            });

            document.body.appendChild(input);
            input.click();
            input.remove();
        },

        exportCurrentPersona() {
            const currentPersona = Storage.getCurrentPersona();
            const json = Storage.exportPersona(currentPersona.id);
            
            const blob = new Blob([json], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${currentPersona.name}-persona.json`;
            a.click();
            URL.revokeObjectURL(url);

            this.app.showToast('角色卡已导出', 'success');
        },

        exportAllPersonas() {
            const json = Storage.exportAllPersonas();
            
            const blob = new Blob([json], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `all-personas-${new Date().toISOString().split('T')[0]}.json`;
            a.click();
            URL.revokeObjectURL(url);

            this.app.showToast('所有角色卡已导出', 'success');
        }
    };

    window.AppPersona = Persona;
})();
