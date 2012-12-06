# -*- encoding: utf-8 -*-

from osv import fields, osv
from copy import copy
import decimal_precision as dp
import netsvc
import re
import time
from tools.safe_eval import safe_eval
from tools.translate import _

LOGGER = netsvc.Logger()

class stock_move(osv.osv):
    _name = "stock.move"
    _inherit = "stock.move"
    
    _columns = {
        'params': fields.dummy(string='Params fields'),
        'parameters_values': fields.related('product_id', 'parameters_values', type='char', size=128, store=False, string="Значения параметров"),
        #'template_id': fields.many2one('product.template', u'Шаблон', required=False, help=u'Шаблон продукции')
    }
    
    def onchange_product_id_editable(self, cr, uid, ids, prod_id=False):
        """Define new function - for change value of extra field 'parameters_values'"""
        
        if not prod_id:
            return {}

        product = self.pool.get('product.product').browse(cr, uid, prod_id)
        result = {
            'parameters_values': product.parameters_values,
        }
        return {'value': result}
    
    def fields_view_get(self, cr, uid, view_id, view_type='form', context=None, toolbar=False, submenu=False):
        fields = super(stock_move, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        arch = ''

        # Add columns with product's parameters
        type_obj = self.pool.get('product.variant.dimension.type')
        types = type_obj.search(cr, uid, [('show_in_tree', '=', True)])
        types = type_obj.browse(cr, uid, types)
        
        for type in types:
            fields['fields'].update({type.description: {
                                                 'type': 'char',#'type': 'many2one',
                                                 #'relation': 'product.variant.dimension.option',
                                                 #'domain': [('dimension_id', '=', type.id)],
                                                 #'required': False,
                                                 'select': True,
                                                 'selectable': True,
                                                 'string': type.name,
                                                 #'states': {'done': [('readonly', True)]},
                                                 #'views': {},
                                                 #'help': type.description,
                                                 #'context': {'state': 'draft'},
                                                 'size': 64,
                                                 }})
            arch += '<field name="%s" />' % type.description
#        if view_type == 'form':
#            arch = '<group>'+arch+'</group>'
        
        fields['arch']=re.sub('<field\s+name=(\'|\")params(\'|\")[^>]+>', arch, fields['arch'].decode('utf-8'))
        
        return fields
    
    def read(self, cr, uid, ids, fields=None, context=None, load="_classic_read"):
        time1 = time.time()
        
        ret = super(stock_move, self).read(cr, uid, ids, fields=fields, context=context, load=load)
        type_obj = self.pool.get('product.variant.dimension.type')
        types = type_obj.search(cr, uid, [('show_in_tree', '=', True)])

        param_fields = []
        if fields and 'product_id' in fields:
            for type in type_obj.browse(cr, uid, types):
                if type.description in fields:
                    param_fields.append(type.description)
        
            product_ids = [item['product_id'] for item in ret]
            product_ids = [i[0] if isinstance(i, tuple) else i for i in product_ids]
            ff = []
            for i, item in enumerate(product_ids):
                if not item:
                    ff.append(i)
            ff.reverse()
            for i in ff:
                del(product_ids[i])
                        
            if param_fields:
                ind = 0
                for product in self.pool.get('product.product').browse(cr, uid, product_ids):
#                    ind = False
#                    for i, item in enumerate(product_ids):
#                        if item == product.id:
#                            ind = i
#                            break
                    for param_value in product.dimension_value_ids:
                        if param_value.dimension_id.show_in_tree and param_value.dimension_id.description in param_fields:   
                            ret[ind].update({param_value.dimension_id.description: param_value.option_id.name})
                    
                    ind += 1
                    
        time2 = time.time()
        if (time2-time1) > 1:
            print "Time for showing parameters - %s" % round(time2-time1)
        return ret
    
    def read_group(self, cr, uid, domain, fields=None, group_by_fields=None, p1=False, p2=False, context=None, sort=False):
        dims = self.pool.get('product.variant.dimension.type').search(cr, uid, [])
        for dim in self.pool.get('product.variant.dimension.type').browse(cr, uid, dims):
            if dim.description in fields:
                del(fields[fields.index(dim.description)])
        ret = super(stock_move, self).read_group(cr, uid, domain, fields, group_by_fields, p1, p2, context, sort)
        return ret   
    
#    def onchange_template_id(self, cr, uid, ids, template_id = False):
#        """Clear parameters and set parameters domain"""
#        type_obj = self.pool.get('product.variant.dimension.type')
#        types = type_obj.search(cr, uid, [('show_in_tree', '=', True)])
#        types = type_obj.browse(cr, uid, types)
#        # Because product_id field cannot be empty, set in it random product, and change it
#        # in writing/creating record
#        random_products = self.pool.get('product.product').search(cr, uid, [])
#        random_product = random_products[0]
#        
#        template = self.pool.get('product.template').browse(cr, uid, template_id)
#        
#        values = {'product_id': random_product, 'product_uom': template.uom_id.id}
#        domain = {}
#        for type in types:
#            values.update({type.description: ''})
#        if not template_id:
#            return {'value': values}
#        
#        value_obj = self.pool.get('product.variant.dimension.value')
#        for type in types:
#           vals = value_obj.search(cr, uid, [('product_tmpl_id', '=', template_id), ('dimension_id', '=', type.id)])
#           curr_domain = []
#           for val in value_obj.browse(cr, uid, vals):
#               curr_domain.append(val.option_id.id)
#           domain.update({type.description: [('id', 'in', curr_domain)]})
#           
#        return {'value': values, 'domain': domain}
            
    
#    def onchange_product_id_multi(self, cr, uid, ids, template_id=False, loc_id=False,
#                            loc_dest_id=False, address_id=False):
#        """ Redefine native function
#        Uses only in incoming products form
#        """
#        if not template_id:
#            return {}
#        lang = False
#        if address_id:
#            addr_rec = self.pool.get('res.partner.address').browse(cr, uid, address_id)
#            if addr_rec:
#                lang = addr_rec.partner_id and addr_rec.partner_id.lang or False
#        ctx = {'lang': lang}
#
#        template = self.pool.get('product.template').browse(cr, uid, [template_id], context=ctx)[0]
#        uos_id  = template.uos_id and template.uos_id.id or False
#        result = {
#            'product_uom': template.uom_id.id,
#            'product_uos': uos_id,
#            'product_qty': 1.00,
#            #'product_uos_qty' : self.pool.get('stock.move').onchange_quantity(cr, uid, ids, prod_id, 1.00, product.uom_id.id, uos_id)['value']['product_uos_qty']
#        }
#        if not ids:
#            result['name'] = template.partner_ref
#        if loc_id:
#            result['location_id'] = loc_id
#        if loc_dest_id:
#            result['location_dest_id'] = loc_dest_id
#        return {'value': result}
    
#    def _modify_by_params(self, cr, uid, vals, ids=False):
#        """Manage product according with its parameters. Use from write and create functions 
#        @param cr
#        @param uid
#        @param <dict>: values to create or write stock_move model
#        @return <dict>: new values to create or write stock_move model
#        """
#        
#        type_obj = self.pool.get('product.variant.dimension.type')
#        option_obj = self.pool.get('product.variant.dimension.option')
#        product_obj = self.pool.get('product.product')
#        tmpl_obj = self.pool.get('product.template')
#        
#        if 'product_id' in vals and vals['product_id']:
#            product = product_obj.browse(cr, uid, vals['product_id'])
#            template = product.product_tmpl_id
#        elif 'template_id' in vals and vals['template_id']:
#            template = tmpl_obj.browse(cr, uid, vals['template_id'])
#            product = False
#        elif ids:
#            if isinstance(ids, long) or isinstance(ids, int):
#                id = ids
#            else:
#                id = ids[0]
#            product = self.browse(cr, uid, id).product_id
#            template = product.product_tmpl_id
#        else:
#            raise osv.except_osv('Error', 'Something is wrong.....');
#        
#        type_ids = type_obj.search(cr, uid, [('show_in_tree', '=', True)])
#        new_params = {}
#        for type in type_obj.browse(cr, uid, type_ids):
#            if type.description in vals and vals[type.description]:
#                if type in template.dimension_type_ids:
#                    new_params.update({'product_tmpl_id_'+str(type.id): option_obj.get_or_create(cr, uid, type.id, vals[type.description])})
#                del(vals[type.description])
#                
#        if new_params:
#            params = {}
#            if product:
#                for param in product.dimension_value_ids:
#                    params.update({'product_tmpl_id_'+str(param.dimension_id.id): param.option_id.id})
#                
#            params.update(new_params)
#            params.update({'tmpl_id': template.id})
#            product_id = product_obj.create_product_from_parameters(cr, uid, params)
#            vals['product_id'] = product_id
#            
#        if 'product_id' in vals:
#            name = product_obj.browse(cr, uid, vals['product_id']).name
#            vals['name'] = name
#        
#        return vals
#    
#    def write(self, cr, uid, ids, vals, context=None):
#        vals = self._modify_by_params(cr, uid, vals, ids)
#        return super(stock_move, self).write(cr, uid, ids, vals, context=None) 
#
#    def create(self, cr, uid, vals, context=None):
#        vals = self._modify_by_params(cr, uid, vals)
#        return super(stock_move, self).create(cr, uid, vals, context=None)
            
    def action_scrap(self, cr, uid, ids, quantity, location_id, context=None):
        res = super(stock_move, self).action_scrap(cr, uid, ids, quantity, location_id, context=context)
        for move in self.browse(cr, uid, ids, context=context):
            self.write(cr, uid, move.id, {'product_qty': move.product_qty-quantity})
        return res
    
stock_move()

class stock_picking(osv.osv):
    _inherit = 'stock.picking'
    _name = 'stock.picking'
    _columns = {
        'tmpl_id': fields.dummy(string='Template', relation='product.template', type='many2one'),
        'multi': fields.dummy(string='Multi fields'),
        'to_production': fields.boolean(u'На производство', help=u"Продукт будет перемещен из расположения по умолчанию на производство")
    }
       
    def get_default_values(self, cr, uid, form_values, related_field, view_name=None):
        """
        Hook-function to get default values for one2many line
        @param obj: psycopg2 cursor
        @param int: user ID
        @param dict: values from form to calculate
        @param dict: None
        """
        
        obj = self.pool.get('stock.move')
        try:
            product_id = form_values['product_id']
            product = self.pool.get('product.product').browse(cr, uid, product_id)

            loc_id = obj._default_location_source(cr, uid, context={'picking_type': form_values['type']})
            loc_dest_id = obj._default_location_destination(cr, uid, context={'picking_type': form_values['type']})
            
            if form_values['type'] == 'internal':
                if 'to_production' in form_values and form_values['to_production']:
                    loc_id = product.product_tmpl_id.location_id_fast.id
                    loc_dest_id = product.product_tmpl_id.property_stock_production.id
                else:
                    loc_dest_id = product.product_tmpl_id.location_id_fast.id
                    loc_id = product.product_tmpl_id.property_stock_production.id
            elif form_values['type'] == 'in':
                loc_dest_id = product.product_tmpl_id.location_id_fast.id
            elif form_values['type'] == 'out':
                loc_id = product.product_tmpl_id.location_id_fast.id
            
            address_id = form_values['address_id']
            count_products = form_values['count_products']
        except KeyError, e:
            raise osv.except_osv('Not enough data for calculate values')

        defaults = obj.onchange_product_id(cr, uid, [], prod_id=product_id, loc_id=loc_id,
                            loc_dest_id=loc_dest_id, address_id=address_id)
        if not defaults or 'value' not in defaults:
            raise osv.except_osv('Error in calculation default values')        
        ret = defaults['value']
        
        ret['product_qty'] = count_products
        ret['date'] = time.strftime('%Y-%m-%d %H:%M:%S')
        ret['date_expected'] = time.strftime('%Y-%m-%d %H:%M:%S')
        
        params = {}#{'template_id': product.product_tmpl_id.id}
        for param in product.dimension_value_ids:
            params[param.dimension_id.description] = param.option_id.name
        ret.update(params)
        
        return ret
        
stock_picking()

class stock_move_split(osv.osv_memory):
    _name = "stock.move.split"
    _inherit = "stock.move.split"
    
    def default_get(self, cr, uid, fields, context=None):
        res = super(stock_move_split, self).default_get(cr, uid, fields, context=context)
        if context.get('active_id'):
            move = self.pool.get('stock.move').browse(cr, uid, context['active_id'], context=context)
            if 'parameters_values' in fields:
                res.update({'parameters_values': move.parameters_values})
        return res
        
    _columns = {
        'parameters_values': fields.char(u"Значения параметров", size=256, readonly=True),
    }
    
stock_move_split()

class stock_production_lot(osv.osv):
    _name = "stock.production.lot"
    _inherit = "stock.production.lot"
    
    _columns = {
        'parameters_values': fields.related('product_id', 'parameters_values', relation="product.product", type="char", string=u"Значения характеристик", readonly=True, store=False),
        'params': fields.dummy(string='Multi fields'),
    }
    
    def fields_view_get(self, cr, uid, view_id, view_type='form', context=None, toolbar=False, submenu=False):
        fields = super(stock_production_lot, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        arch = ''

        # Add columns with product's parameters
        type_obj = self.pool.get('product.variant.dimension.type')
        types = type_obj.search(cr, uid, [('show_in_tree', '=', True)])
        types = type_obj.browse(cr, uid, types)
        
        for type in types:
            fields['fields'].update({type.description: {
                                                 'type': 'char',
                                                 'select': True,
                                                 'selectable': True,
                                                 'string': type.name,
                                                 'size': 64,
                                                 }})
            arch += '<field name="%s" />' % type.description
        
        fields['arch']=re.sub('<field\s+name=(\'|\")params(\'|\")[^>]+>', arch, fields['arch'].decode('utf-8'))
        
        return fields
    
    def read(self, cr, uid, ids, fields=None, context=None, load="_classic_read"):
        time1 = time.time()
        
        ret = super(stock_production_lot, self).read(cr, uid, ids, fields=fields, context=context, load=load)
        type_obj = self.pool.get('product.variant.dimension.type')
        types = type_obj.search(cr, uid, [('show_in_tree', '=', True)])

        param_fields = []
        if fields and 'product_id' in fields:
            for type in type_obj.browse(cr, uid, types):
                if type.description in fields:
                    param_fields.append(type.description)
        
            product_ids = [item['product_id'] for item in ret]
            product_ids = [i[0] if isinstance(i, tuple) else i for i in product_ids]
            ff = []
            for i, item in enumerate(product_ids):
                if not item:
                    ff.append(i)
            ff.reverse()
            for i in ff:
                del(product_ids[i])
                        
            if param_fields:
                ind = 0
                for product in self.pool.get('product.product').browse(cr, uid, product_ids):
                    for param_value in product.dimension_value_ids:
                        if param_value.dimension_id.show_in_tree and param_value.dimension_id.description in param_fields:   
                            ret[ind].update({param_value.dimension_id.description: param_value.option_id.name})
                    
                    ind += 1
                    
        time2 = time.time()
        if (time2-time1) > 1:
            print "Time for showing parameters - %s" % round(time2-time1)
        return ret
    
    def read_group(self, cr, uid, domain, fields=None, group_by_fields=None, p1=False, p2=False, context=None, sort=False):
        dims = self.pool.get('product.variant.dimension.type').search(cr, uid, [])
        for dim in self.pool.get('product.variant.dimension.type').browse(cr, uid, dims):
            if dim.description in fields:
                del(fields[fields.index(dim.description)])
        ret = super(stock_production_lot, self).read_group(cr, uid, domain, fields, group_by_fields, p1, p2, context, sort)
        return ret   
    
stock_production_lot()
        