# -*- encoding: utf-8 -*-

from osv import fields, osv
import decimal_precision as dp
import re

class mrp_product_produce(osv.osv_memory):
    _name = "mrp.product.produce"
    _inherit = "mrp.product.produce"
    
    _columns = {
        'product_qty': fields.float('Select Quantity', digits_compute=dp.get_precision('Product UoM'), required=False),
        'products_qty': fields.char('Количество продуктов', size=512, required=False),
    }
    
    def create(self, cr, uid, vals, context=None):
        products_qty = '{'
        for key, val in vals.items():
            if key.startswith('move_created_id_qty_'):
                products_qty += key.replace('move_created_id_qty_', '')+':'+str(val)+','
        products_qty = products_qty[:-1]
        products_qty += '}'
        vals['products_qty'] = products_qty
        create_id = super(mrp_product_produce, self).create(cr, uid, vals, context=context)
        return create_id
    
    def write(self, cr, uid, ids, vals, context=None):
        products_qty = '{'
        for key, val in vals.items():
            if key.startswith('move_created_id_qty_'):
                products_qty += key.replace('move_created_id_qty_', '')+':'+str(val)+','
        products_qty = products_qty[:-1]
        products_qty += '}'
        vals['products_qty'] = products_qty
        ret = super(mrp_product_produce, self).write(cr, uid, ids, vals, context=context)
        return ret
    
    def do_produce(self, cr, uid, ids, context=None):
        production_id = context.get('active_id', False)
        assert production_id, "Production Id should be specified in context as a Active ID"
        data = self.browse(cr, uid, ids[0], context=context)
        products = eval(data.products_qty)
        self.pool.get('mrp.production').action_produce(cr, uid, production_id,
                            products, data.mode, context=context)
        return {}
    
    def fields_view_get(self, cr, uid, view_id, view_type='form', context=None, toolbar=False, submenu=False):
        ret = super(mrp_product_produce, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        if view_type == 'form':
            prod = self.pool.get('mrp.production').browse(cr, uid,
                                context['active_id'], context=context)
            add_arch = ''
            for item in prod.move_created_ids:
                add_arch += '<field name="move_created_id_qty_%s" /><newline/>' % item.product_id.id
                ret['fields']['move_created_id_qty_'+str(item.product_id.id)] = {
                            'digits': (16, 3),
                            'required': True,
                            'selectable': True,
                            'string': item.product_id.product_name,
                            'type': 'float',
                            'views': {},
                }
                
                # Calc product qty
#                cnt = 0.0
#                for move in prod.move_created_ids2:
#                    if move.product_id == item.product_id:
#                        if not move.scrapped:
#                            cnt += move.product_qty
#                cnt = (item.product_qty - cnt) or item.product_qty
                self._defaults.update({'move_created_id_qty_'+str(item.product_id.id): item.product_qty})
                
            del ret['fields']['product_qty']
            #del self._defaults['product_qty']
            ret['arch'] = re.sub('<field\s+name=(\'|\")product_qty(\'|\")[^>]+>', add_arch, ret['arch'])

        return ret