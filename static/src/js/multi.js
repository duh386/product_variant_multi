openerp.product_variant_multi.multi = function(openerp) {
	var QWeb = openerp.web.qweb,
	      _t =  openerp.web._t,
	     _lt = openerp.web._lt;
	
	var eAlert = function(title, message)
	{
		$('<div>' + QWeb.render('CrashManagerWarning', {error: {
			code: 200,
			data: {
				//debug: '',
				fault_code: message,
				//type: 'server_exception'
			}
		}}) + '</div>').dialog({
	        title: title,
	        buttons: [
	            {text: _t("Ok"), click: function() { $(this).dialog("close"); }}
	        ]
	    });
	}
     

	/* Extensions for search for multi characteristics */
	
	openerp.web.SearchView.include({
	    on_loaded: function(data) 
	    {
	        this.fields_view = data.fields_view;
	        if (data.fields_view.type !== 'search' ||
	            data.fields_view.arch.tag !== 'search') {
	                throw new Error(_.str.sprintf(
	                    "Got non-search view after asking for a search view: type %s, arch root %s",
	                    data.fields_view.type, data.fields_view.arch.tag));
	        }
	        var self = this,
	           lines = this.make_widgets(
	                data.fields_view['arch'].children,
	                data.fields_view.fields);
	
	        // for extended search view
	        var ext = new openerp.web.search.ExtendedSearch(this, this.model);
	        lines.push([ext]);
	        this.extended_search = ext;
	        
	        //Осторожно - костыль! (VSkorina)
	        if(this.fields_view.selected)
	            for(prop in this.fields_view.selected)
	                this.defaults[prop] = this.fields_view.selected[prop];
	        //-----------------------------------
	        var render = QWeb.render("SearchView", {
	            'view': data.fields_view['arch'],
	            'lines': lines,
	            'defaults': this.defaults
	        });
	        
	        this.$element.html(render);
	
	        var f = this.$element.find('form');
	        this.$element.find('form')
	                .submit(this.do_search)
	                .bind('reset', this.do_clear);
	        // start() all the widgets
	        var widget_starts = _(lines).chain().flatten().map(function (widget) {
	            return widget.start();
	        }).value();
	
	        $.when.apply(null, widget_starts).then(function () {
	            self.ready.resolve();
	        });
	
	        this.reload_managed_filters();
	    },
	});


	openerp.web.search.SelectionField.include({
	
	    render: function (defaults) {
	        if (!defaults[this.attrs.name]) {
	            defaults[this.attrs.name] = false;
	        }
	        
	        // ASavchenko
	        // Внимание - костыль!
	        // Добавляем обработчик onchange на все <selection name='product_tmpl_id' />
	        field_name=this.attrs['name'];
	        field_widget=this.attrs['widget'];
	        
	        if (field_name=='product_tmpl_id' && field_widget=='selection')
	        {
	            $('select[name='+field_name+']').die('change'); 
	            $('select[name='+field_name+']').live('change', {obj:this, field_name:field_name},this.onchange_template);
	        }
	        return this._super(defaults);
	        
	    },
	    
	    onchange_template: function (event)
	    {
	        objSelectionField = event.data.obj;  
	        
	        if (objSelectionField.view.model=='product.product')
	        {
	            template_id=objSelectionField.get_value();
	            objSelectionField.view.defaults['product_tmpl_id']=template_id*1;
	            objSelectionField.view.inputs=[];
	            ctx=objSelectionField.view.dataset.get_context();
	            if('add' in ctx)
	                ctx.add({'template_id' : template_id, 'hide_empty_params': true});
	            else{
	                ctx.template_id = template_id;
	            	ctx.hide_empty_params = true;
	            }
	            
	            objSelectionField.rpc("/web/searchview/load", {
	                model: objSelectionField.view.model,
	                view_id: objSelectionField.view.view_id,
	                context: ctx
	            }, objSelectionField.view.on_loaded);
	        }
	    },
	    
	});

	/* ASavchenko
	 * Внимание - костыль
	 * При доработке формы поиска товара при открытии ее в окне виджета результат поиска
	 * добавляется к существующему.
	 * Добавляем костыль - удаление блока с существующим списком результатов при 
	 * количестве блоков > 1
	 */
	openerp.web.ListView.include({
		
	    on_loaded: function(data, grouped) {
		
			this._super.apply(this, arguments)
	
			var lists=$('div.ui-dialog table.oe-listview-content:visible').parent();
			elem=lists[lists.length-2]
			if (window.elem && data.model == 'product.product' && $(elem).next().length)
			{
				$(elem).remove();
			}
	
		}
		
	});

/* Extensions for orders form - in fact, creating new widget from "many2many" */

/* Redefining from view_form.js */
	var commands = {
	    // (0, _, {values})
	    CREATE: 0,
	    'create': function (values) {
	        return [commands.CREATE, false, values];
	    },
	    // (1, id, {values})
	    UPDATE: 1,
	    'update': function (id, values) {
	        return [commands.UPDATE, id, values];
	    },
	    // (2, id[, _])
	    DELETE: 2,
	    'delete': function (id) {
	        return [commands.DELETE, id, false];
	    },
	    // (3, id[, _]) removes relation, but not linked record itself
	    FORGET: 3,
	    'forget': function (id) {
	        return [commands.FORGET, id, false];
	    },
	    // (4, id[, _])
	    LINK_TO: 4,
	    'link_to': function (id) {
	        return [commands.LINK_TO, id, false];
	    },
	    // (5[, _[, _]])
	    DELETE_ALL: 5,
	    'delete_all': function () {
	        return [5, false, false];
	    },
	    // (6, _, ids) replaces all linked records with provided ids
	    REPLACE_WITH: 6,
	    'replace_with': function (ids) {
	        return [6, false, ids];
	    }
	};
	
	openerp.web.form.widgets.map['many2many_order'] = 'openerp.web.form.FieldMany2Many_order';
	openerp.web.page.readonly.map['many2many_order'] = 'openerp.web.page.FieldMany2ManyReadonly';
	
	openerp.web.form.widgets.map['selection_create_product'] = 'openerp.web.form.SelectionCreateProduct';
	openerp.web.page.readonly.map['selection_create_product'] = 'openerp.web.form.FieldSelection';

	openerp.web.form.FieldMany2Many_order = openerp.web.form.Field.extend({
	    template: 'FieldMany2Many',
	    multi_selection: false,
	    init: function(view, node) {
	        this._super(view, node);
	        this.list_id = _.uniqueId("many2many");
	        this.is_loaded = $.Deferred();
	        this.initial_is_loaded = this.is_loaded;
	        this.is_setted = $.Deferred();
	    },
	    start: function() {
	        this._super.apply(this, arguments);
	
	        var self = this;
	
	        this.dataset = new openerp.web.form.Many2ManyDataSet(this, this.field.relation);//new openerp.web.form.Many2ManyDataSet_order(this, this.field.relation);
	
	        this.dataset.m2m = this;
	        this.dataset.on_unlink.add_last(function(ids) {
	            self.on_ui_change();
	        });
	
	        this.is_setted.then(function() {
	            self.load_view();
	        });
	        
	        /* ASavchenko
	         * WARNING - dirt hack
	         * Save $element in global variable 
	         * for hide confirm button and trigger for it in searchForm
	         */
	        many2many_order_element = self.$element;
	    },
	    set_value: function(value) {
	        value = value || [];
	        if (value.length >= 1 && value[0] instanceof Array) {
	            value = value[0][2];
	        }
	        this._super(value);
	        this.dataset.set_ids(value);
	        var self = this;
	        self.reload_content();
	        this.is_setted.resolve();
	    },
	    get_value: function() {
	        return [commands.replace_with(this.dataset.ids)];
	    },
	    validate: function() {
	        this.invalid = false;
	    },
	    is_readonly: function() {
	        return this.readonly || this.force_readonly;
	    },
	    load_view: function() {
	        var self = this;
	        this.list_view = new openerp.web.form.Many2ManyListView_order_form(this, this.dataset, false, {
	                    'addable': self.is_readonly() ? null : _t("Add"),
	                    'deletable': self.is_readonly() ? false : true,
	                    'selectable': self.multi_selection,
	                    'isClarkGable': self.is_readonly() ? false : true
	        });
	     
	        var embedded = (this.field.views || {}).tree;
	        if (embedded) {
	            this.list_view.set_embedded_view(embedded);
	        }
	        this.list_view.m2m_field = this;
	        var loaded = $.Deferred();
	        this.list_view.on_loaded.add_last(function() {
	            self.initial_is_loaded.resolve();
	            loaded.resolve();
	        });
	        $.async_when().then(function () {
	            self.list_view.appendTo($("#" + self.list_id));
	        });
	        
	
	        return loaded;
	    },
	    reload_content: function() {
	        var self = this;
	        this.is_loaded = this.is_loaded.pipe(function() {
	            return self.list_view.reload_content();
	        });
	    },
	    update_dom: function() {
	        this._super.apply(this, arguments);
	        var self = this;
	        if (this.previous_readonly !== this.readonly) {
	            this.previous_readonly = this.readonly;
	            if (this.list_view) {
	                this.is_loaded = this.is_loaded.pipe(function() {
	                    self.list_view.stop();
	                    return $.when(self.load_view()).then(function() {
	                        self.reload_content();
	                    });
	                });
	            }
	        }
	        $(many2many_order_element).parent().next().hide();
	    }
	});

	openerp.web.form.Many2ManyListView_order = openerp.web.ListView.extend({
			
		  init: function(parent, dataset, view_id, options) {
		
			  var self = this;
			  //this._super(parent);
			  this._super.apply(this, arguments);
			  this.set_default_options(_.extend({}, this.defaults, options || {}));
			  this.dataset = dataset;
			  this.model = dataset.model;
			  this.view_id = view_id;
			  this.previous_colspan = null;
			  this.colors = null;
	
			  this.columns = [];
			
			  //this.records = new Collection();
			
			  this.set_groups(new openerp.web.ListView.Groups_order(this));
			
			  if (this.dataset instanceof openerp.web.DataSetStatic) {
			      this.groups.datagroup = new openerp.web.StaticDataGroup(this.dataset);
			  } else {
			      this.groups.datagroup = new openerp.web.DataGroup(
			          this, this.model,
			          dataset.get_domain(),
			          dataset.get_context(),
			          {});
			      this.groups.datagroup.sort = this.dataset._sort;
			  }
			
			  this.page = 0;		
			  this.no_leaf = false;
		},
		
	    do_add_record: function () {
	        var pop = new openerp.web.form.SelectCreatePopup_order(this);
	        pop.select_element(
	            this.model,
	            {
	                title: _t("Add: ") + this.name
	            },
	            new openerp.web.CompoundDomain(this.m2m_field.build_domain(), ["!", ["id", "in", this.m2m_field.dataset.ids]]),
	            this.m2m_field.build_context()
	        );
	        var self = this;
	        pop.on_select_elements.add(function(element_ids) {
	            _.each(element_ids, function(element_id) {
	                if(! _.detect(self.dataset.ids, function(x) {return x == element_id;})) {
	                    self.dataset.set_ids([].concat(self.dataset.ids, [element_id]));
	                    self.m2m_field.on_ui_change();
	                    self.reload_content();
	                }
	            });
	        });
	    },
	    do_activate_record: function(index, id) {
	        var self = this;
	        var pop = new openerp.web.form.FormOpenPopup(this);
	        pop.show_element(this.dataset.model, id, this.m2m_field.build_context(), {
	            title: _t("Open: ") + this.name,
	            readonly: this.widget_parent.is_readonly()
	        });
	        pop.on_write_completed.add_last(function() {
	            self.reload_content();
	        });
	    }
	});

	openerp.web.form.Many2ManyListView_order_form = openerp.web.form.Many2ManyListView_order.extend({
		_template: 'ListView_order_form'
	});

	openerp.web.form.SelectCreatePopup_order = openerp.web.OldWidget.extend({
	    template: "SelectCreatePopup_order",
	    /**
	     * options:
	     * - initial_ids
	     * - initial_view: form or search (default search)
	     * - disable_multiple_selection
	     * - alternative_form_view
	     * - create_function (defaults to a naive saving behavior)
	     * - parent_view
	     * - child_name
	     * - form_view_options
	     * - list_view_options
	     * - read_function
	     */
	    select_element: function(model, options, domain, context) {
	        var self = this;
	        this.model = model;
	        this.domain = domain || [];
	        this.context = context || {};
	        this.options = _.defaults(options || {}, {"initial_view": "search", "create_function": function() {
	            return self.create_row.apply(self, arguments);
	        }, read_function: null});
	        this.initial_ids = this.options.initial_ids;
	        this.created_elements = [];
	        this.render_element();
	        openerp.web.form.dialog(this.$element, {
	            close: function() {
	                self.check_exit();
	            },
	            title: options.title || ""
	        });
	        this.start();
	    },
	    start: function() {
	    	
	        this._super();
	        var self = this;
	        
	        this.dataset = new openerp.web.ProxyDataSet(this, this.model,
	            this.context);
	        this.dataset.create_function = function() {
	            return self.options.create_function.apply(null, arguments).then(function(r) {
	                self.created_elements.push(r.result);
	            });
	        };
	        this.dataset.write_function = function() {
	            return self.write_row.apply(self, arguments);
	        };
	        this.dataset.read_function = this.options.read_function;
	        this.dataset.parent_view = this.options.parent_view;
	        this.dataset.child_name = this.options.child_name;
	        this.dataset.on_default_get.add(this.on_default_get);
	        if (this.options.initial_view == "search") {
	            self.rpc('/web/session/eval_domain_and_context', {
	                domains: [],
	                contexts: [this.context]
	            }, function (results) {
	                var search_defaults = {};
	                _.each(results.context, function (value, key) {
	                    var match = /^search_default_(.*)$/.exec(key);
	                    if (match) {
	                        search_defaults[match[1]] = value;
	                    }
	                });
	                self.setup_search_view(search_defaults);
	            });
	        } else { // "form"
	            this.new_object();
	        }
	        
	        self.$element.find('table').eq(0).find('tr').eq(0).after(QWeb.render("SelectCreatePopup_order.notify_area"));
	        
	    },
	    setup_search_view: function(search_defaults) {
	        var self = this;
	
	        if (this.searchview) {
	            this.searchview.stop();
	        }
	        this.searchview = new openerp.web.SearchView(this,
	                this.dataset, false,  search_defaults);
	        this.searchview.on_search.add(function(domains, contexts, groupbys) {
	            if (self.initial_ids) {
	                self.do_search(domains.concat([[["id", "in", self.initial_ids]], self.domain]),
	                    contexts, groupbys);
	                self.initial_ids = undefined;
	            } else {
	                self.do_search(domains.concat([self.domain]), contexts.concat(self.context), groupbys);
	            }
	        });
	        this.searchview.on_loaded.add_last(function () {
	 
	            self.view_list = new openerp.web.form.SelectCreateListView(self,
	                    self.dataset, false,
	                    _.extend({'deletable': false,
	                        'selectable': !self.options.disable_multiple_selection
	                    }, self.options.list_view_options || {}));
	            self.view_list.popup = self;
	            self.view_list.appendTo($("#" + self.element_id + "_view_list")).pipe(function() {
	                self.view_list.do_show();
	            }).pipe(function() {
	                self.searchview.do_search();
	            });
	            self.view_list.on_loaded.add_last(function() {
	          	
	                var $buttons = self.view_list.$element.find(".oe-actions");
	                $buttons.prepend(QWeb.render("SelectCreatePopup_order.search.buttons"));
	                
	                var $cbutton = $buttons.find(".oe_selectcreatepopup-search-close");
	                $cbutton.click(function() {
	                    self.stop();
	                });
	
	                //New button - add lines without closing window
	                var $abutton = $buttons.find(".oe_selectcreatepopup-search-add");
	                $abutton.click(function() {
	                    self.on_select_elements(self.selected_ids);
	                	$checkboxes=self.$element.find('.oe-record-selector > input:checkbox:checked');
	                	$checkboxes.add('input:checkbox.all-record-selector').removeAttr('checked');
	                	$p='<p class="order_product_notify">'+_t('Products added: ')+$checkboxes.length+'</p>';
	                	self.$element.find('.order_product_notify_area').append($p);
	                	
	                	//Confirm button trigger
	                	$(many2many_order_element).parent().next().find('button').click();
	                });
	                //Clear notifies if new form opened
	                var $nbutton = $buttons.find(".oe-list-add");
	                $nbutton.click(function() {
	                	self.$element.find('.order_product_notify_area').html('');
	                });
	                
	            });
	        });
	        this.searchview.appendTo($("#" + this.element_id + "_search"));
	    },
	    do_search: function(domains, contexts, groupbys) {
	        var self = this;
	        this.rpc('/web/session/eval_domain_and_context', {
	            domains: domains || [],
	            contexts: contexts || [],
	            group_by_seq: groupbys || []
	        }, function (results) {
	            self.view_list.do_search(results.domain, results.context, results.group_by);
	        });
	    },
	    create_row: function() {
	        var self = this;
	        var wdataset = new openerp.web.DataSetSearch(this, this.model, this.context, this.domain);
	        wdataset.parent_view = this.options.parent_view;
	        wdataset.child_name = this.options.child_name;
	        return wdataset.create.apply(wdataset, arguments);
	    },
	    write_row: function() {
	        var self = this;
	        var wdataset = new openerp.web.DataSetSearch(this, this.model, this.context, this.domain);
	        wdataset.parent_view = this.options.parent_view;
	        wdataset.child_name = this.options.child_name;
	        return wdataset.write.apply(wdataset, arguments);
	    },
	    on_select_elements: function(element_ids) {
	    },
	    on_click_element: function(ids) {
	        this.selected_ids = ids || [];
	        if(this.selected_ids.length > 0) {
	            //this.$element.find(".oe_selectcreatepopup-search-select").removeAttr('disabled');
	            this.$element.find(".oe_selectcreatepopup-search-add").removeAttr('disabled');
	        } else {
	            //this.$element.find(".oe_selectcreatepopup-search-select").attr('disabled', "disabled");
	            this.$element.find(".oe_selectcreatepopup-search-add").attr('disabled', "disabled");
	        }
	    },
	    new_object: function() {
	        var self = this;
	        if (this.searchview) {
	            this.searchview.hide();
	        }
	        if (this.view_list) {
	            this.view_list.$element.hide();
	        }
	        this.dataset.index = null;
	        this.view_form = new openerp.web.FormView(this, this.dataset, false, self.options.form_view_options);
	        if (this.options.alternative_form_view) {
	            this.view_form.set_embedded_view(this.options.alternative_form_view);
	        }
	        this.view_form.appendTo(this.$element.find("#" + this.element_id + "_view_form"));
	        this.view_form.on_loaded.add_last(function() {
	            var $buttons = self.view_form.$element.find(".oe_form_buttons");
	            $buttons.html(QWeb.render("SelectCreatePopup.form.buttons", {widget:self}));
	            var $nbutton = $buttons.find(".oe_selectcreatepopup-form-save-new");
	            $nbutton.click(function() {
	                $.when(self.view_form.do_save()).then(function() {
	                    self.view_form.reload_mutex.exec(function() {
	                        self.view_form.on_button_new();
	                    });
	                });
	            });
	            var $nbutton = $buttons.find(".oe_selectcreatepopup-form-save");
	            $nbutton.click(function() {
	                $.when(self.view_form.do_save()).then(function() {
	                    self.view_form.reload_mutex.exec(function() {
	                        self.check_exit();
	                    });
	                });
	            });
	            var $cbutton = $buttons.find(".oe_selectcreatepopup-form-close");
	            $cbutton.click(function() {
	                self.check_exit();
	            });
	        });
	        this.view_form.do_show();
	    },
	    check_exit: function() {
	        if (this.created_elements.length > 0) {
	            this.on_select_elements(this.created_elements);
	        }
	        this.stop();
	    },
	    on_default_get: function(res) {}
	});

	openerp.web.ListView.List_order_rows = openerp.web.ListView.List.extend({
		
		init: function (group, opts) {
		
		    var self = this;
		    this.group = group;
		    this.view = group.view;
		    this.session = this.view.session;
		
		    this.options = opts.options;
		    this.columns = opts.columns;
		    this.dataset = opts.dataset;
		    this.records = opts.records;
		
		    this.record_callbacks = {
		        'remove': function (event, record) {
		            var $row = self.$current.find(
		                    '[data-id=' + record.get('id') + ']');
		            var index = $row.data('index');
		            $row.remove();
		            self.refresh_zebra(index);
		        },
		        'reset': function () { return self.on_records_reset(); },
		        'change': function (event, record) {
		            var $row = self.$current.find('[data-id=' + record.get('id') + ']');
		            $row.replaceWith(self.render_record(record));
		        },
		        'add': function (ev, records, record, index) {
		            var $new_row = $('<tr>').attr({
		                'data-id': record.get('id')
		            });
		
		            if (index === 0) {
		                $new_row.prependTo(self.$current);
		            } else {
		                var previous_record = records.at(index-1),
		                    $previous_sibling = self.$current.find(
		                            '[data-id=' + previous_record.get('id') + ']');
		                $new_row.insertAfter($previous_sibling);
		            }
		
		            self.refresh_zebra(index, 1);
		        }
		    };
		    _(this.record_callbacks).each(function (callback, event) {
		        this.records.bind(event, callback);
		    }, this);
		
		    this.$_element = $('<tbody class="ui-widget-content" style="display: none;">')
		        .appendTo(document.body)
		        .delegate('th.oe-record-selector', 'click', function (e) {
		            e.stopPropagation();
		            var selection = self.get_selection();
		            $(self).trigger(
		                    'selected', [selection.ids, selection.records]);
		        })
		        .delegate('td.oe-record-delete button', 'click', function (e) {
		            e.stopPropagation();
		            var $row = $(e.target).closest('tr');
		            $(self).trigger('deleted', [[self.row_id($row)]]);
		        })
		        .delegate('td.oe-field-cell button', 'click', function (e) {
		            e.stopPropagation();
		            var $target = $(e.currentTarget),
		                  field = $target.closest('td').data('field'),
		                   $row = $target.closest('tr'),
		              record_id = self.row_id($row);
		
		            // note: $.data converts data to number if it's composed only
		            // of digits, nice when storing actual numbers, not nice when
		            // storing strings composed only of digits. Force the action
		            // name to be a string
		            $(self).trigger('action', [field.toString(), record_id, function () {
		                return self.reload_record(self.records.get(record_id));
		            }]);
		        })
		        .delegate('a', 'click', function (e) {
		            e.stopPropagation();
		        })
		        .delegate('tr', 'click', function (e) {
		            e.stopPropagation();
		            var row_id = self.row_id(e.currentTarget);
		            if (row_id !== undefined) {
		                if (!self.dataset.select_id(row_id)) {
		                    throw "Could not find id in dataset"
		                }
		                var view;
		                if ($(e.target).is('.oe-record-edit-link-img')) {
		                    view = 'form';
		                }
		                self.row_clicked(e, view);
		            }
		        });
		}
	});

	openerp.web.ListView.Groups_order = openerp.web.ListView.Groups.extend({
		
		render_dataset: function (dataset) {
		    var self = this,
		        list = new openerp.web.ListView.List_order_rows(this, {
		            options: this.options,
		            columns: this.columns,
		            dataset: dataset,
		            records: this.records
		        });
		    this.bind_child_events(list);
		
		    var view = this.view,
		       limit = view.limit(),
		           d = new $.Deferred(),
		        page = this.datagroup.openable ? this.page : view.page;
		
		    var fields = _.pluck(_.select(this.columns, function(x) {return x.tag == "field"}), 'name');
		    var options = { offset: page * limit, limit: limit, context: {bin_size: true} };
		    //TODO xmo: investigate why we need to put the setTimeout
		    $.async_when().then(function() {dataset.read_slice(fields, options).then(function (records) {
		        // FIXME: ignominious hacks, parents (aka form view) should not send two ListView#reload_content concurrently
		        if (self.records.length) {
		            self.records.reset(null, {silent: true});
		        }
		        if (!self.datagroup.openable) {
		            view.configure_pager(dataset);
		        } else {
		            if (dataset.size() == records.length) {
		                // only one page
		                self.$row.find('td.oe-group-pagination').empty();
		            } else {
		                var pages = Math.ceil(dataset.size() / limit);
		                self.$row
		                    .find('.oe-pager-state')
		                        .text(_.str.sprintf(_t("%(page)d/%(page_count)d"), {
		                            page: page + 1,
		                            page_count: pages
		                        }))
		                    .end()
		                    .find('button[data-pager-action=previous]')
		                        .attr('disabled', page === 0)
		                    .end()
		                    .find('button[data-pager-action=next]')
		                        .attr('disabled', page === pages - 1);
		            }
		        }
		
		        self.records.add(records, {silent: true});
		        list.render();
		        d.resolve(list);
		    });});
		    return d.promise();
		},
		render_groups: function (datagroups) {
	        var self = this;
	        var placeholder = this.make_fragment();
	        _(datagroups).each(function (group) {
	            if (self.children[group.value]) {
	                self.records.proxy(group.value).reset();
	                delete self.children[group.value];
	            }
	            var child = self.children[group.value] = new openerp.web.ListView.Groups_order(self.view, {
	                records: self.records.proxy(group.value),
	                options: self.options,
	                columns: self.columns
	            });
	            self.bind_child_events(child);
	            child.datagroup = group;
	
	            var $row = child.$row = $('<tr>');
	            if (group.openable && group.length) {
	                $row.click(function (e) {
	                    if (!$row.data('open')) {
	                        $row.data('open', true)
	                            .find('span.ui-icon')
	                                .removeClass('ui-icon-triangle-1-e')
	                                .addClass('ui-icon-triangle-1-s');
	                        child.open(self.point_insertion(e.currentTarget));
	                    } else {
	                        $row.removeData('open')
	                            .find('span.ui-icon')
	                                .removeClass('ui-icon-triangle-1-s')
	                                .addClass('ui-icon-triangle-1-e');
	                        child.close();
	                    }
	                });
	            }
	            placeholder.appendChild($row[0]);
	
	            var $group_column = $('<th class="oe-group-name">').appendTo($row);
	            // Don't fill this if group_by_no_leaf but no group_by
	            if (group.grouped_on) {
	                var row_data = {};
	                row_data[group.grouped_on] = group;
	                var group_column = _(self.columns).detect(function (column) {
	                    return column.id === group.grouped_on; });
	                try {
	                    $group_column.html(openerp.web.format_cell(
	                        row_data, group_column, {
	                            value_if_empty: _t("Undefined"),
	                            process_modifiers: false
	                    }));
	                } catch (e) {
	                    $group_column.html(row_data[group_column.id].value);
	                }
	                if (group.length && group.openable) {
	                    // Make openable if not terminal group & group_by_no_leaf
	                    $group_column.prepend('<span class="ui-icon ui-icon-triangle-1-e" style="float: left;">');
	                } else {
	                    // Kinda-ugly hack: jquery-ui has no "empty" icon, so set
	                    // wonky background position to ensure nothing is displayed
	                    // there but the rest of the behavior is ui-icon's
	                    $group_column.prepend('<span class="ui-icon" style="float: left; background-position: 150px 150px">');
	                }
	            }
	            self.indent($group_column, group.level);
	            // count column
	            $('<td>').text(group.length).appendTo($row);
	
	            if (self.options.selectable) {
	                $row.append('<td>');
	            }
	            if (self.options.isClarkGable) {
	                $row.append('<td>');
	            }
	            _(self.columns).chain()
	                .filter(function (column) {return !column.invisible;})
	                .each(function (column) {
	                    if (column.meta) {
	                        // do not do anything
	                    } else if (column.id in group.aggregates) {
	                        var value = group.aggregates[column.id];
	                        $('<td class="oe-number">')
	                            .html(openerp.web.format_value(value, column))
	                            .appendTo($row);
	                    } else {
	                        $row.append('<td>');
	                    }
	                });
	            if (self.options.deletable) {
	                $row.append('<td class="oe-group-pagination">');
	            }
	        });
	        return placeholder;
	    },
	});

	openerp.web.form.SelectionCreateProduct = openerp.web.form.Field.extend({
	    template: 'SelectionCreateProduct',
		init: function(view, node) {
	        var self = this;
	        this._super(view, node);
	        this.values = _.clone(this.field.selection);
	        _.each(this.values, function(v, i) {
	            if (v[0] === false && v[1] === '') {
	                self.values.splice(i, 1);
	            }
	        });
	        this.values.unshift([false, '']);
	    },
	    start: function() {
	        // Flag indicating whether we're in an event chain containing a change
	        // event on the select, in order to know what to do on keyup[RETURN]:
	        // * If the user presses [RETURN] as part of changing the value of a
	        //   selection, we should just let the value change and not let the
	        //   event broadcast further (e.g. to validating the current state of
	        //   the form in editable list view, which would lead to saving the
	        //   current row or switching to the next one)
	        // * If the user presses [RETURN] with a select closed (side-effect:
	        //   also if the user opened the select and pressed [RETURN] without
	        //   changing the selected value), takes the action as validating the
	        //   row
	        var ischanging = false;
	        this._super.apply(this, arguments);
	        this.$element.find('select')
	            .change(this.on_ui_change)
	            .change(function () { ischanging = true; })
	            .change(function(){
	            	//console.log($('.select-create-product').parent().parent().parent());
	            	$('.select-create-product').parent().parent().parent().parent().parent().parent().find('button').eq(0).trigger('click');
	            })
	            .click(function () { ischanging = false; })
	            .keyup(function (e) {
	                if (e.which !== 13 || !ischanging) { return; }
	                e.stopPropagation();
	                ischanging = false;
	            });
	    },
	    set_value: function(value) {
	        value = value === null ? false : value;
	        value = value instanceof Array ? value[0] : value;
	        this._super(value);
	        var index = 0;
	        for (var i = 0, ii = this.values.length; i < ii; i++) {
	            if (this.values[i][0] === value) index = i;
	        }
	        this.$element.find('select')[0].selectedIndex = index;
	    },
	    set_value_from_ui: function() {
	        this.value = this.values[this.$element.find('select')[0].selectedIndex][0];
	        this._super();
	    },
	    update_dom: function() {
	        this._super.apply(this, arguments);
	        this.$element.find('select').prop('disabled', this.readonly);
	    },
	    validate: function() {
	        var value = this.values[this.$element.find('select')[0].selectedIndex];
	        this.invalid = !(value && !(this.required && value[0] === false));
	    },
	    focus: function($element) {
	        this._super($element || this.$element.find('select:first'));
	    }
	});

}

