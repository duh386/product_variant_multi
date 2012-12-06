# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from osv import fields, osv
import re
from tools.translate import _

class create_product(osv.osv_memory):
    _name = 'create.product'
    _description = 'Create product from template'
    
    
    def fields_view_get(self, cr, uid, view_id, view_type='form', context=None, toolbar=False, submenu=False):
        fields=super(create_product, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
    
        if 'active_id' in context:
            if 'active_model' in context and self._name == context['active_model']:
                line=self.browse(cr, uid, context['active_id'])
                tmpl_id = line.tmpl_id.id
            else:
                tmpl_id = context['active_id']
        else:
            return fields

        query="""
                SELECT dv.dimension_id, dv.option_id, dt.name as type_name, dop.name as option_name 
                FROM product_variant_dimension_value as dv
                LEFT JOIN product_variant_dimension_type as dt ON dt.id=dv.dimension_id
                LEFT JOIN product_variant_dimension_option as dop ON dop.id=dv.option_id
                WHERE dv.product_tmpl_id=%s
            """ % tmpl_id
        cr.execute(query)
        multi_fields=cr.fetchall()
        multi_types={}
        multi_types_str=''
        # Add variant fields
        if multi_fields:
            for row in multi_fields:
                # 0 - type_id, 1 - option_id, 2 - type_name, 3 - option_name
                field_name='product_tmpl_id_'+str(row[0])
                if field_name not in multi_types:
                    multi_types[field_name]={
                        'context': {},
                        'domain': [],
                        'relation': 'product.variant.dimension.option',
                        'required': True,
                        'selectable': True,
                        'selection': [(row[1], row[3])],
                        'string': row[2],
                        'type': 'many2one',
                        'views': {},
                    }
                    multi_types_str+='<newline /><field name="%s" widget="selection" required="1" />' % field_name 
                else:
                    multi_types[field_name]['selection'].append((row[1], row[3]))
            for key, val in multi_types.items():
                fields['fields'][key]=val
            fields['arch']=re.sub('<field\s+name=(\'|\")multi(\'|\")[^>]+>', multi_types_str, fields['arch'])
        else:
            fields['arch']=re.sub('<field\s+name=(\'|\")multi(\'|\")[^>]+>', '    ', fields['arch'])
                
        # Add all template variants for widget SelectionCreateProduct
        if view_type == 'form':
            tmpl_ids = self.pool.get('product.template').search(cr, uid, [], context=context)
            templates = self.pool.get('product.template').browse(cr, uid, tmpl_ids, context=context)
            
            fields['fields']['tmpl_id']['selection'] = []
            
            for rec in templates:
                fields['fields']['tmpl_id']['selection'].append((rec.id, rec.name))
        
        return fields
    
    def _get_tmpl_id(self,cr, uid, ctx):
        if 'active_id' in ctx:
            if 'active_model' in ctx and self._name == ctx['active_model']:
                line=self.browse(cr, uid, ctx['active_id'])
                tmpl_id = line.tmpl_id.id
            else:
                tmpl_id = ctx['active_id']
            return tmpl_id
        else:
            return False
    
    _columns = {
        'tmpl_id': fields.many2one('product.template', 'Template'),
        'multi': fields.dummy(string='Multi fields'),
        'multi_values': fields.text('Multi values', translate=False, required=False),
    }
    
    _defaults = {
        'tmpl_id': _get_tmpl_id
    }
    
    def do_create_product(self, cr, uid, ids, context=None):
        
        vals = eval(self.browse(cr, uid, ids[0], context=context).multi_values)
        for key, val in vals.items():
            if key.startswith('product_tmpl_id_') and not val:
                raise osv.except_osv('Warning', _('Fill all characteristics'))
        
        product_id = self.pool.get('product.product').create_product_from_parameters(cr, uid, vals, context=context)
        if product_id:
            self.unlink(cr, uid, ids, context=context)
        return {}
    
    def create(self, cr, uid, vals, context=None):
        vals['multi_values'] = str(vals)
        create_id = super(create_product, self).create(cr, uid, vals, context=context)
        return create_id

    
    def write(self, cr, uid, ids, vals, context=None):
        multi_values = self.browse(cr, uid, ids[0]).multi_values
        multi_values = eval(multi_values)
        for key, val in vals.items():
            multi_values[key] = val
        
        vals['multi_values'] = str(multi_values)
        super(create_product, self).write(cr, uid, ids, vals, context=context)
        return True
    
    def do_refresh_view(self, cr, uid, ids, context):
        
        line=self.browse(cr, uid, ids)[0]
        if not line:
            return dict(error=_('Wrong data'))
        
        return {
            'domain': "[]",
            'name': 'Make product from template',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'create.product',
            'view_id': False,
            'context': {
                        #'default_tmpl_id': line.tmpl_id.id,
                        },
            'type': 'ir.actions.act_window',
            'target': 'new',
        }

    
#    def do_create(self, cr, uid, ids, context):
#
#        move_id = context['move_id']
#        for rec in self.browse(cr, uid, ids, context=context):
#                product_to = rec.product_to_id
#                
#
#        for rec in self.pool.get('stock.move').browse(cr, uid, [move_id], context=None):
#                stock_move = rec
#
#        product_from = stock_move.product_id
#        
#        bom_id = False
#        
#        for rec in self.pool.get('mrp.bom').search(cr, uid, [('product_id','=', product_to.id)]):
#                bom_id = rec
#
#        if not bom_id:
#            raise osv.except_osv('Операция не возможна!', 'Для данного продукта не определена спецификация!')
#                
#        bom_in = False
#        
#        for rec in self.pool.get('mrp.bom').browse(cr, uid, [bom_id]):
#                bom = rec
#                
#        for line in bom.bom_lines:
#                if line.product_id.id == product_from.id:
#                    bom_in = True
#                qty = stock_move.product_qty / line.product_qty
#                
#        if not bom_in:
#            raise osv.except_osv('Операция не возможна!', 'В спецификацию выбранного продукта не входит исходный продукт!')
#                
#        pr_id = self.pool.get('mrp.production').create(cr, uid, {
#            'product_id' : product_to.id,
#            'product_uom' : product_to.product_tmpl_id.uom_id.id,
#            'location_src_id' : stock_move.location_dest_id.id,
#            'location_dest_id' : stock_move.location_dest_id.id,
#            'product_qty' : qty,
##            'state' : 'done'
#        })
#        
#        self.pool.get('mrp.production').action_confirm(cr, uid, [pr_id])
#        self.pool.get('mrp.production').force_production(cr, uid, [pr_id])
#        
#        self.pool.get('mrp.production').action_ready(cr, uid, [pr_id])
#            
#        self.pool.get('mrp.production').action_in_production(cr, uid, [pr_id])
#        self.pool.get('mrp.production').action_produce(cr, uid, pr_id, qty, 'consume_produce', context=context)
#        self.pool.get('mrp.production').action_production_end(cr, uid, [pr_id])
#        
#        return {}
    


    
create_product()