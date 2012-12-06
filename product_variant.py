# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2008 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    Copyright (C) 2010-2011 Akretion (www.akretion.com). All Rights Reserved
#    @author Sebatien Beau <sebastien.beau@akretion.com>
#    @author Alexis de Lattre <alexis.delattre@akretion.com>
#       update to use a single "Generate/Update" button & price computation code
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from osv import fields, osv
from copy import copy
import decimal_precision as dp
import netsvc
import re
import time
# Lib to eval python code with security
from tools.safe_eval import safe_eval
from tools.translate import _

LOGGER = netsvc.Logger()

#
# Dimensions Definition
#
class product_variant_dimension_type(osv.osv):
    _name = "product.variant.dimension.type"
    _description = "Dimension Type"

    _columns = {
        'description': fields.char('Description', size=64, translate=True),
        'name' : fields.char('Dimension', size=64, required=True),
        'sequence' : fields.integer('Sequence', help="The product 'variants' code will use this to order the dimension values"),
        'option_ids' : fields.one2many('product.variant.dimension.option', 'dimension_id', 'Dimension Option'),
        'product_tmpl_id': fields.many2many('product.template', 'product_template_dimension_rel', 'dimension_id', 'template_id', 'Product Template'),
        'allow_custom_value': fields.boolean('Allow Custom Value', help="If true, custom values can be entered in the product configurator"),
        'mandatory_dimension': fields.boolean('Mandatory Dimension', help="If false, variant products will be created with and without this dimension"),
        'show_in_tree': fields.boolean(u'Отображать в списке продукции'),
    }

    _defaults = {
        'mandatory_dimension': lambda *a: 1,
    }
    
    _order = "sequence, name"

    def name_search(self, cr, user, name='', args=None, operator='ilike', context=None, limit=None):
        if context is None:
            context = {}
        if not context.get('product_tmpl_id', False):
            args = None
        return super(product_variant_dimension_type, self).name_search(cr, user, name, args, 'ilike', None, None)

product_variant_dimension_type()

class product_variant_dimension_option(osv.osv):
    _name = "product.variant.dimension.option"
    _description = "Dimension Option"

    def _get_dimension_values(self, cr, uid, ids, context=None):
        return self.pool.get('product.variant.dimension.value').search(cr, uid, [('dimension_id', 'in', ids)], context=context)

    _columns = {
        'name' : fields.char('Dimension Value', size=64, required=True),
        'code' : fields.char('Code', size=64),
        'sequence' : fields.integer('Sequence'),
        'dimension_id' : fields.many2one('product.variant.dimension.type', 'Dimension Type', ondelete='cascade'),
    }
    
    def create(self, cr, uid, vals, context=None):
        return super(product_variant_dimension_option, self).create(cr, uid, vals, context=context)

    _order = "dimension_id, sequence, name"
    
    def get_or_create(self, cr, uid, dimension_id, value_name, context=None):
        """Return ID of option, create if not exists
        @param cr
        @param uid
        @param <int>: dimension ID
        @param <str>: option name
        @return <int>: ID of option
        """
        ids = self.search(cr, uid, [('name', '=', value_name), ('dimension_id', '=', dimension_id)])
        if not len(ids):
            id = self.create(cr, uid, {'name': value_name, 'code': value_name, 'dimension_id': dimension_id})
        else:
            id = ids[0]
        return id    
        
product_variant_dimension_option()


class product_variant_dimension_value(osv.osv):
    _name = "product.variant.dimension.value"
    _description = "Dimension Value"
    _rec_name = "option_id"

    def unlink(self, cr, uid, ids, context=None):
        for value in self.browse(cr, uid, ids, context=context):
            if value.product_ids:
                product_list = '\n    - ' + '\n    - '.join([product.name for product in value.product_ids])
                raise osv.except_osv(_('Dimension value can not be removed'), _("The value %s is used in the product : %s \n Please remove this product before removing the value"%(value.option_id.name, product_list)))
        return super(product_variant_dimension_value, self).unlink(cr, uid, ids, context)

    def _get_dimension_values(self, cr, uid, ids, context=None):
        return self.pool.get('product.variant.dimension.value').search(cr, uid, [('dimension_id', 'in', ids)], context=context)

    _columns = {
        'option_id' : fields.many2one('product.variant.dimension.option', 'Option', required=True),
        'sequence' : fields.integer('Sequence'),
        'price_extra' : fields.float('Sale Price Extra', digits_compute=dp.get_precision('Sale Price')),
        'price_margin' : fields.float('Sale Price Margin', digits_compute=dp.get_precision('Sale Price')),
        'cost_price_extra' : fields.float('Cost Price Extra', digits_compute=dp.get_precision('Purchase Price')),
        'dimension_id' : fields.related('option_id', 'dimension_id', type="many2one", relation="product.variant.dimension.type", string="Dimension Type", store=True),
        'product_tmpl_id': fields.many2one('product.template', 'Product Template', ondelete='cascade'),
        'dimension_sequence': fields.related('dimension_id', 'sequence', string="Related Dimension Sequence",#used for ordering purposes in the "variants"
             store={
                'product.variant.dimension.type': (_get_dimension_values, ['sequence'], 10),
            }),
        'product_ids': fields.many2many('product.product', 'product_product_dimension_rel', 'dimension_id', 'product_id', 'Variant', readonly=True),
        'active' : fields.boolean('Active?', help="If false, this value will be not use anymore for generating variant"),
    }

    _defaults = {
        'active': lambda *a: 1,
    }

    _order = "dimension_sequence, sequence, option_id"
    
    def onchange_dimension_type(self, cr, uid, ids, dimension_id):
        dim = self.pool.get('product.variant.dimension.type').browse(cr, uid, dimension_id)
        option_ids = []
        for option in dim.option_ids:
            option_ids.append(option.id)
        return {'domain': {'option_id': [('id', 'in', option_ids)]}}

product_variant_dimension_value()


class product_template(osv.osv):
    _inherit = "product.template"
    _name = "product.template"

    _columns = {
        'dimension_type_ids':fields.many2many('product.variant.dimension.type', 'product_template_dimension_rel', 'template_id', 'dimension_id', 'Dimension Types'),
        'value_ids': fields.one2many('product.variant.dimension.value', 'product_tmpl_id', 'Dimension Values'),
        'variant_ids':fields.one2many('product.product', 'product_tmpl_id', 'Variants'),
        'variant_model_name':fields.char('Variant Model Name', size=64, required=True, help='[_o.dimension_id.name_] will be replaced by the name of the dimension and [_o.option_id.code_] by the code of the option. Example of Variant Model Name : "[_o.dimension_id.name_] - [_o.option_id.code_]"'),
        'variant_model_name_separator':fields.char('Variant Model Name Separator', size=64, help= 'Add a separator between the elements of the variant name'),
        'code_generator' : fields.char('Code Generator', size=64, help='enter the model for the product code, all parameter between [_o.my_field_] will be replace by the product field. Example product_code model : prefix_[_o.variants_]_suffixe ==> result : prefix_2S2T_suffix'),
        'is_multi_variants' : fields.boolean('Is Multi Variants?'),
        'variant_track_production' : fields.boolean('Track Production Lots on variants ?'),
        'variant_track_incoming' : fields.boolean('Track Incoming Lots on variants ?'),
        'variant_track_outgoing' : fields.boolean('Track Outgoing Lots on variants ?'),
    
        'register_uom': fields.many2one('product.uom', 'Ед. изм. учета', required=True, readonly=False, help=u"Учетная ед. изм. продукта"),
        'register_uom_rule': fields.char('Правила расчета', size=64, required=False, readonly=False, help="Правило пересчета дефолтной ед. изм. в учетную. Понимает знаки '+', '*', '/', '-', цифры и описание(description) измерения"),
    
        'location_id_fast': fields.many2one('stock.location', u'Расположение по умолчанию', required=True, help=u'Это расположение будет использоваться по умолчанию для данного вида продукта при создании внутреннего перемещения' ),
    }
    
    _defaults = {
        'variant_model_name': lambda *a: '[_o.dimension_id.name_] - [_o.option_id.code_]',
        'variant_model_name_separator': lambda *a: ' - ',
        'is_multi_variants' : lambda *a: False,
        'register_uom': 1,
        'register_uom_rule': '',
    }

    _order = 'name'
    
    def insert_data(self, cr, uid, ids, context=None):
        import xlrd
        inventory_line_obj = self.pool.get('stock.inventory.line')
        move_obj = self.pool.get('stock.move')
        tpl_obj = self.pool.get('product.template')
        product_obj = self.pool.get('product.product')

        def get_product(tpl_name, params):
            """
            @param <str> name template
            @param <dict>{
                <int>dimension_id: <str>option_name
                .............
            }
            Return <int>product_id"""
            
            tpl = tpl_obj.search(cr, uid, [('name', '=', tpl_name)])
            if not len(tpl):
                tpl_id = tpl_obj.create(cr, uid, {
                             'name': tpl_name,
                             'type': 'product',
                             'is_multi_variants': True,
                             'procure_method': 'make_to_order',
                             'register_uom': 10,
                             'register_uom_rule': 'length*width/1000000',
                             'dimension_type_ids': [(6, 0, [1, 2, 3, 4])],
                             })
                print 'Tpl "%s" was created' % tpl_name
            else:
                tpl_id = tpl[0]
                
            type_obj = self.pool.get('product.variant.dimension.type')
            opt_obj = self.pool.get('product.variant.dimension.option')
            value_obj = self.pool.get('product.variant.dimension.value')
            # Vals for creating product
            vals = {'tmpl_id': tpl_id}
            for type_id, opt_name in params.items():
                # Check, if option exists
                opt_ids = opt_obj.search(cr, uid, [('name', '=', opt_name), ('dimension_id', '=', type_id)])
                if not len(opt_ids):
                    opt_id = opt_obj.create(cr, uid, {'dimension_id': type_id, 
                                             'code': opt_name,
                                             'name': opt_name,
                                             })
                    print 'Option "%s" was created for type %s' % (opt_name, type_id)
                else:
                    opt_id = opt_ids[0]
                # Set option to template
                value_ids = value_obj.search(cr, uid, [('dimension_id', '=', type_id), 
                                                      ('option_id', '=', opt_id),
                                                      ('product_tmpl_id', '=', tpl_id)])
                if not len(value_ids):
                    value_id = value_obj.create(cr, uid, {'dimension_id': type_id,
                                                          'option_id': opt_id,
                                                          'product_tmpl_id': tpl_id})
                else:
                    value_id = value_ids[0]
                vals.update({'product_tmpl_id_'+str(type_id): opt_id})
                
            # Get product
            product_id = product_obj.create_product_from_parameters(cr, uid, vals)
            
            return product_id
        
        def set_count(inv_id, product_id, product_uom, loc, cnt):
            line_id = inventory_line_obj.create(cr, uid, {
                'inventory_id': inv_id,
                'location_id': loc,
                'product_id': product_id,
                'product_uom': product_uom,
                'product_qty': cnt
            })
            
            move_id = move_obj.create(cr, uid, {
                'name': 'INV:%s:Init inventory'%inv_id,
                'product_id': product_id,
                'product_uom': product_uom,
                'product_qty': cnt,
                'location_dest_id': loc,
                'location_id': 5, # Inventory loss
                'state': 'done'
            })
            #Create move_rel
            cr.execute("""
                INSERT INTO stock_inventory_move_rel (inventory_id, move_id)
                VALUES (%s, %s)
            """, (inv_id, move_id))
            return move_id
            

        f = xlrd.open_workbook(u'/home/duh386/zov/МАТЕРИАЛЫ АВГУСТ_наш4.xls')
        inv_id = self.pool.get('stock.inventory').create(cr, uid, {'name': 'New inventory', 'state': 'done'})


        # FIRST SHEET
#        sh = f.sheet_by_index(0)
#        i=0
#        for rx in range(sh.nrows):
#            i += 1
#            if i > 61:
#                continue
#            row = sh.row_values(rx)
#            
#            try:
#                type = str(int(row[0]))
#            except ValueError:
#                type = row[0]
#            l_w = str(row[1])
#            if not l_w:
#                continue
#            count = row[36]
#            
#            if type and type in ('3', '4', '6', '8', '10', '12', '16', '18', '19', '22', '28', '30', '40'):
#                tpl_name = 'Лист МДФ_'+type
#            elif type:
#                tpl_name = type
#                
#            if not tpl_name:
#                print '------EMPTY tpl_name in row %s' % i
#                continue
#            else:
#                print 'Set tpl "%s" in row %s' % (tpl_name, i)
#                
#            lw = l_w.split('х')
#            try:
#                l = str(int(float(lw[0].replace(',', '.'))*1000))
#                w = str(int(float(lw[1].replace(',', '.'))*1000))
#            except ValueError:
#                continue
#            
#            prod_id = get_product(tpl_name, {2: l, 3: w})
#            product = self.pool.get('product.product').browse(cr, uid, prod_id)
#            
#            # Set product to warehouse
#            if count:
#                move_id = set_count(inv_id, prod_id, product.uom_id.id, 20, count)
#                print 'Set count %s for product "%s"' % (count, product.name)
        
        # SECOND SHEET
#        sh = f.sheet_by_index(1)
#        i=0
#        for rx in range(sh.nrows):
#            i += 1
#            row = sh.row_values(rx)
#                        
#            try:
#                type = str(int(row[0]))
#                w = str(int(row[1]))
#            except ValueError:
#                continue
#            
#            count = {}
#            count['2070'] = row[2]
#            count['2300'] = row[3]
#            count['2500'] = row[4]
#            count['2620'] = row[5]
#            count['2800'] = row[6]
#            #count['2850'] = row[7]
#            
#            tpl_name = 'Полоса пиленная МДФ_'+type
#            print 'Set tpl "%s" in row %s' % (tpl_name, i)
#            
#            # Use every length separately
#            for l in ('2070', '2300', '2500', '2620', '2800'):   
#                prod_id = get_product(tpl_name, {2: l, 3: w})
#                product = self.pool.get('product.product').browse(cr, uid, prod_id)
#                # Set product to warehouse
#                if count[l]:
#                    move_id = set_count(inv_id, prod_id, product.uom_id.id, 24, count[l])
#                    print 'Set count %s for product "%s"' % (count[l], product.name)


        # THIRD SHEET
#        sh = f.sheet_by_index(2)
#        i=0
#        for rx in range(sh.nrows):
#            i += 1
#            row = sh.row_values(rx)
#
#            tpl_name = str(row[0])
#            if not tpl_name:
#                continue
#            d = str(int(row[1]))
#            try:
#                w = str(int(row[2])-2)
#            except ValueError:
#                pass
#            
#            count = {}
#            count['2070'] = row[3]
#            count['2300'] = row[4]
#            count['2500'] = row[5]
#            count['2620'] = row[6]
#            count['2800'] = row[7]
#            count['2850'] = row[8]
#
#            tpl_name = tpl_name + ' /0'
#            print 'Set tpl "%s" in row %s' % (tpl_name, i)
#            
#            # Use every length separately
#            for l in ('2070', '2300', '2500', '2620', '2800', '2850'):   
#                prod_id = get_product(tpl_name, {2: l, 3: w, 4: d})
#                product = self.pool.get('product.product').browse(cr, uid, prod_id)
#                # Set product to warehouse
#                if count[l]:
#                    move_id = set_count(inv_id, prod_id, product.uom_id.id, 25, count[l])
#                    print 'Set count %s for product "%s"' % (count[l], product.name)
        
        # FIFTH SHEET
#        sh = f.sheet_by_index(5)
#        i=0
#        for rx in range(sh.nrows):
#            i += 1
#            row = sh.row_values(rx)
#
#            tpl_name = str(row[0])
#            if not tpl_name:
#                continue
#            try:
#                w = str(int(row[1]))
#            except ValueError:
#                pass
#            try:
#                d = str(int(row[2]))
#            except ValueError:
#                pass
#            color = row[3]
#            count = {}
#            count['1860'] = row[4]
#            count['2070'] = row[5]
#            count['2200'] = row[6]
#            count['2440'] = row[7]
#            count['2620'] = row[8]
#            count['2800'] = row[9]
#            count['2850'] = row[10]
#
#            print 'Set tpl "%s" in row %s' % (tpl_name, i)
#              
#            # Set product for each length
#            for l in ('1860', '2070', '2200', '2440', '2620', '2800', '2850'):
#                params = {1: color, 2: l, 3: w, 4: d}
#                prod_id = get_product(tpl_name, params)
#                product = self.pool.get('product.product').browse(cr, uid, prod_id)
#                # Set product to warehouse
#                if count[l]:
#                    move_id = set_count(inv_id, prod_id, product.uom_id.id, 38, count[l])
#                    print 'Set count %s for product "%s"' % (count[l], product.product_name)
        
        print 'Success'
        #raise osv.except_osv('Bla', 'Blabla')

                
        return {}

    def to_excel(self, cr, uid, ids, context=None):        
        import xlwt
        b = xlwt.Workbook()
        sheet = b.add_sheet('data')
        cat_obj = self.pool.get('product.category')
        cats = cat_obj.search(cr, uid, [])
        i = 1
        for cat in cat_obj.browse(cr, uid, cats):
            sheet.write(i, 1, cat.id)
            sheet.write(i, 2, cat_obj.name_get(cr, uid, [cat.id])[0][1])
            i += 1
        
        loc_obj = self.pool.get('stock.location')
        locs = loc_obj.search(cr, uid, [])
        i = 1
        for loc in loc_obj.browse(cr, uid, locs):
            sheet.write(i, 4, loc.id)
            sheet.write(i, 5, loc_obj.name_get(cr, uid, [loc.id])[0][1])
            i += 1
            
#            cat_name = cat_obj.name_get(cr, uid, [cat.id])[0][1]
#            cat_name = cat_name.replace(' / ', '-')
#            try:
#                sheet = b.add_sheet(cat_name[-29:])
#            except Exception, e:
#                print 'Error creating sheet with name "%s" - %s' % (cat_name.decode('utf-8'), e.message)
#                continue
#            tpls = self.search(cr, uid, [('categ_id', '=', cat.id)])
#            tpls = self.browse(cr, uid, tpls)
#            i = 1
#            
#            sheet.write(0, 0, u'Наименование')
#            j = 1
#            if len(tpls):
#                for type in tpls[0].dimension_type_ids:
#                    sheet.write(0, j, type.description)
#                    j += 1
#                
#            for tpl in tpls:
#                sheet.write(i, 0, tpl.name)
#                i += 1
    
        b.save('/tmp/categ_locations.xls')
        return {}
    
    def unlink(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        for template in self.browse(cr, uid, ids, context):
            super(product_template, self).unlink(cr, uid, [template.id], context)
        return True
        
    
    def create(self, cr, uid, vals, context=None):
        return super(product_template, self).create(cr, uid, vals, context)

    def write(self, cr, uid, ids, vals, context=None):
        # When your write the name on a simple product from the menu product template you have to update the name on the product product
        # Two solution was posible overwritting the write function or overwritting the read function
        # I choose to overwrite the write function because read is call more often than the write function
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}

        res = super(product_template, self).write(cr, uid, ids, vals.copy(), context=context)

        if not context.get('iamthechild', False):
            obj_product = self.pool.get('product.product')
            if vals.get('is_multi_variants', 'wrong') != 'wrong':
                if vals['is_multi_variants']:
                    prod_tmpl_ids_simple = False
                else:
                    prod_tmpl_ids_simple = ids
            else:            
                prod_tmpl_ids_simple = self.search(cr, uid, [['id', 'in', ids], ['is_multi_variants', '=', False]], context=context)
            
#            if prod_tmpl_ids_simple:
#                #NB in the case that the user have just unchecked the option 'is_multi_variants' without changing any field the vals_to_write is empty
#                vals_to_write = obj_product.get_vals_to_write(vals)
#                if vals_to_write:
#                    ctx = context.copy()
#                    ctx['iamthechild'] = True
#                    product_ids = obj_product.search(cr, uid, [['product_tmpl_id', 'in', prod_tmpl_ids_simple]])
#                    obj_product.write(cr, uid, product_ids, vals_to_write, context=ctx)
        return res

    def add_all_option(self, cr, uid, ids, context=None):
        #Reactive all unactive values
        value_obj = self.pool.get('product.variant.dimension.value')
        for template in self.browse(cr, uid, ids, context=context):
            values_ids = value_obj.search(cr, uid, [['product_tmpl_id','=', template.id], '|', ['active', '=', False], ['active', '=', True]], context=context)
            value_obj.write(cr, uid, values_ids, {'active':True}, context=context)
            existing_option_ids = [value.option_id.id for value in value_obj.browse(cr, uid, values_ids,context=context)]
            vals = {'value_ids' : []}
            for dim in template.dimension_type_ids:
                for option in dim.option_ids:
                    if not option.id in existing_option_ids:
                        vals['value_ids'] += [[0, 0, {'option_id': option.id}]]
            self.write(cr, uid, template.id, vals, context=context)    
        return True

    def get_products_from_product_template(self, cr, uid, ids, context=None):
        product_tmpl = self.read(cr, uid, ids, ['variant_ids'], context=context)
        return [id for vals in product_tmpl for id in vals['variant_ids']]
    
    def copy(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}
        default = default.copy()
        default.update({'variant_ids':False,})
        return super(product_template, self).copy(cr, uid, id, default, context)

    def copy_translations(self, cr, uid, old_id, new_id, context=None):
        if context is None:
            context = {}
        # avoid recursion through already copied records in case of circular relationship
        seen_map = context.setdefault('__copy_translations_seen',{})
        if old_id in seen_map.setdefault(self._name,[]):
            return
        seen_map[self._name].append(old_id)
        return super(product_template, self).copy_translations(cr, uid, old_id, new_id, context=context)

    def _create_variant_list(self, cr, ids, uid, vals, context=None):
        
        def cartesian_product(args):
            if len(args) == 1: return [x and [x] or [] for x in args[0]]
            return [(i and [i] or []) + j for j in cartesian_product(args[1:]) for i in args[0]]
        
        return cartesian_product(vals)

    def product_product_variants_vals(self, cr, uid, product_temp, variant, context=None):
        """Return Product Product Values Dicc
        :product_temp Object
        :variant list ids
        :return vals
        """

        vals = {}
        vals['track_production'] = product_temp.variant_track_production
        vals['track_incoming'] = product_temp.variant_track_incoming
        vals['track_outgoing'] = product_temp.variant_track_outgoing
        vals['product_tmpl_id'] = product_temp.id
        vals['dimension_value_ids'] = [(6,0,variant)]

        return vals

    def button_generate_variants(self, cr, uid, ids, context=None):
        """Generate Product Products from variants (product.template)
        :ids: list
        :return products (list of products)
        """
        if context is None:
            context = {}
        variants_obj = self.pool.get('product.product')
        temp_val_list = []

        for product_temp in self.browse(cr, uid, ids, context):
            #for temp_type in product_temp.dimension_type_ids:
            #    temp_val_list.append([temp_type_value.id for temp_type_value in temp_type.value_ids] + (not temp_type.mandatory_dimension and [None] or []))
                #TODO c'est quoi ça??
                # if last dimension_type has no dimension_value, we ignore it
            #    if not temp_val_list[-1]:
            #        temp_val_list.pop()
            res = {}
            for value in product_temp.value_ids:
                if res.get(value.dimension_id, False):
                    res[value.dimension_id] += [value.id]
                else:
                    res[value.dimension_id] = [value.id]
            for dim in res:
                temp_val_list += [res[dim] + (not dim.mandatory_dimension and [None] or [])]

            if temp_val_list:
                list_of_variants = self._create_variant_list(cr, uid, ids, temp_val_list, context)
                existing_product_ids = variants_obj.search(cr, uid, [('product_tmpl_id', '=', product_temp.id)])
                existing_product_dim_value = variants_obj.read(cr, uid, existing_product_ids, ['dimension_value_ids'])
                list_of_variants_existing = [x['dimension_value_ids'] for x in existing_product_dim_value]
                for x in list_of_variants_existing:
                    x.sort()
                for x in list_of_variants:
                    x.sort()
                list_of_variants_to_create = [x for x in list_of_variants if not x in list_of_variants_existing]
                
                LOGGER.notifyChannel('product_variant_multi', netsvc.LOG_INFO, "variant existing : %s, variant to create : %s" % (len(list_of_variants_existing), len(list_of_variants_to_create)))
                count = 0
                for variant in list_of_variants_to_create:
                    count += 1
                    
                    vals = self.product_product_variants_vals(cr, uid, product_temp, variant, context)   
                    product_id = variants_obj.create(cr, uid, vals, {'generate_from_template' : True})
                    if count%50 == 0:
                        cr.commit()
                        LOGGER.notifyChannel('product_variant_multi', netsvc.LOG_INFO, "product created : %s" % (count,))
                LOGGER.notifyChannel('product_variant_multi', netsvc.LOG_INFO, "product created : %s" % (count,))

        product_ids = self.get_products_from_product_template(cr, uid, ids, context=context)

        # FIRST, Generate/Update variant names ('variants' field)
        LOGGER.notifyChannel('product_variant_multi', netsvc.LOG_INFO, "Starting to generate/update variant names...")
        self.pool.get('product.product').build_variants_name(cr, uid, product_ids, context=context)
        LOGGER.notifyChannel('product_variant_multi', netsvc.LOG_INFO, "End of the generation/update of variant names.")
        # SECOND, Generate/Update product codes and properties (we may need variants name for that)
        LOGGER.notifyChannel('product_variant_multi', netsvc.LOG_INFO, "Starting to generate/update product codes and properties...")
        self.pool.get('product.product').build_product_code_and_properties(cr, uid, product_ids, context=context)
        LOGGER.notifyChannel('product_variant_multi', netsvc.LOG_INFO, "End of the generation/update of product codes and properties.")
        LOGGER.notifyChannel('product_variant_multi_advanced', netsvc.LOG_INFO, "Starting to generate/update product names...")

        context['variants_values'] = {}
        for product in self.pool.get('product.product').read(cr, uid, product_ids, ['variants'], context=context):
            context['variants_values'][product['id']] = product['variants']
        self.pool.get('product.product').build_product_name(cr, uid, product_ids, context=context)
        LOGGER.notifyChannel('product_variant_multi_advanced', netsvc.LOG_INFO, "End of generation/update of product names.")

        return product_ids
        
product_template()


class product_product(osv.osv):
    _inherit = "product.product"
    _name = "product.product"
    
    def init(self, cr):
        #For the first installation if you already have product in your database the name of the existing product will be empty, so we fill it
        cr.execute("update product_product set product_name=name_template where product_name is null;")
        return True
  
    def unlink(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        context['unlink_from_product_product']=True
        return super(product_product, self).unlink(cr, uid, ids, context)

    def build_product_name(self, cr, uid, ids, context=None):
        return self.build_product_field(cr, uid, ids, 'product_name', context=None)

    def build_product_field(self, cr, uid, ids, field, context=None):
        if context is None:
            context = {}
        def get_description_sale(product):
            return self.parse(cr, uid, product, product.product_tmpl_id.description_sale, context=context)

        def get_product_name(product):
            if context.get('variants_values', False):
                return (product.product_tmpl_id.name or '' )+ ' ' + (context['variants_values'][product.id] or '')
            return (product.product_tmpl_id.name or '' )+ ' ' + (product.variants or '')

        context['is_multi_variants']=True
        obj_lang=self.pool.get('res.lang')
        lang_ids = obj_lang.search(cr, uid, [('translatable','=',True)], context=context)
        lang_code = [x['code'] for x in obj_lang.read(cr, uid, lang_ids, ['code'], context=context)]
        for code in lang_code:
            context['lang'] = code
            for product in self.browse(cr, uid, ids, context=context):
                new_field_value = eval("get_" + field + "(product)") # TODO convert to safe_eval
                cur_field_value = safe_eval("product." + field, {'product': product})
                if new_field_value != cur_field_value:
                    self.write(cr, uid, product.id, {field: new_field_value}, context=context)
        return True
    
    def create_product_from_parameters(self, cr, uid, vals, context=None):
        """Check, if product with this parameters exists.
        IF not, create it.
        @param <obj>: psql cursor obj
        @param <int>: current user id
        @param <dict>: dict of parameters in format:
        {   tmpl_id: <id_template>,
            product_tmpl_id_<dimension_id_1>: <option_id_1(can be 'new_'+option_name)>
            ...,
            product_tmpl_id_<dimension_id_N>: <option_id_N>
        }
        
        @return <int>: product_id
        """
        if 'tmpl_id' not in vals:
            raise osv.except_osv('Warning', _('Wrong data'))
        
        product_obj = self.pool.get('product.product')
        multi_type_obj = self.pool.get('product.variant.dimension.type')
        multi_option_obj = self.pool.get('product.variant.dimension.option')
        multi_value_obj = self.pool.get('product.variant.dimension.value')
        
        tmpl_id = int(vals['tmpl_id'])
        multi_fields = {}
        for key, val in vals.items():
            if key.startswith('product_tmpl_id_'):
                dim_key = int(key[16:])
                opt_key = val
                # Create new option, if it not exists
                if hasattr(opt_key, 'startswith') and opt_key.startswith('new_'):
                    opt_val = opt_key[4:]
                    opt_key = multi_option_obj.create(cr, uid, {
                                                  'name': opt_val,
                                                  'code': opt_val,
                                                  'dimension_id': dim_key,
                                                  })
                else:
                    opt_key = int(opt_key)
                
                multi_fields[dim_key] = opt_key
        
        template = self.pool.get('product.template').browse(cr, uid, tmpl_id, context)
        if not template:
            raise osv.except_osv('Warning', _('Wrong template'))
        
        product_name = template.name
        parameters_values = ''
        multi_value_ids = []
        if multi_fields:
            # Set options to template, if it not exists in it
            for dim, opt in multi_fields.items():
                tmps = multi_value_obj.search(cr, uid, [('dimension_id', '=', dim), ('option_id', '=', opt), ('product_tmpl_id', '=', tmpl_id)])
                if not tmps:
                    multi_value_obj.create(cr, uid, {
                         'product_tmpl_id': tmpl_id,
                         'dimension_id': dim,
                         'option_id': opt,
                    })
                    
            product = product_obj.multi_search_one(cr, uid, tmpl_id, multi_fields)
            if len(product) == 1:
                p = product_obj.browse(cr, uid, product[0])
                msg = u'Продукт "%s" был использован' % p.product_name
                self.log(cr, uid, product[0], msg)
                return product[0]
            elif len(product) > 1:
                raise osv.except_osv('Error', 'Количество таких продуктов > 1')
                              
            for key, val in multi_fields.items():
                key = int(key)
                val = int(val)
                multi_value_id = multi_value_obj.search(cr, uid, [('dimension_id', '=', key), ('option_id', '=', val), ('product_tmpl_id', '=', tmpl_id)], context=context)
                if not multi_value_id:
                    raise osv.except_osv('Warning', _('Wrong dimension'))
                else:
                    multi_value_ids.append(multi_value_id[0])
                
                type = multi_type_obj.browse(cr, uid, key)
                type_desc = type.description or type.name
                type_name = type.name
                option = multi_option_obj.browse(cr, uid, val)
                option_code = option.code or option.name
                option_name = option.name
                
                product_name += ' %s - %s ' % (type_desc, option_code)
  
        product_id = product_obj.create(cr, uid, {
                                                      'product_tmpl_id': tmpl_id, 
                                                      'product_name': product_name,
                                                  }, context=context)
        if not product_id:
            raise osv.except_osv('Warning', _('Error in creating product'))
        else:
            product_name = self.pool.get('product.product').browse(cr, uid, product_id).product_name
            msg = _(u'Продукт "%s" был создан') % product_name
            self.log(cr, uid, product_id, msg)
            
        for val in multi_value_ids:
            query = """ INSERT INTO product_product_dimension_rel 
            (dimension_id, product_id) 
            VALUES
            (%s, %s)""" % (val, product_id)
            cr.execute(query)
        
        return product_id
    
    
    def name_get(self, cr, user, ids, context=None):
        """Redefine native function for adding into name extra field 'parameters_values'"""
        if context is None:
            context = {}
        if not len(ids):
            return []
        def _name_get(d):
            name = d.get('name','')
            code = d.get('default_code',False)
            if code:
                name = '[%s] %s' % (code,name)
#            if d.get('variants'):
#                name = name + ' - %s' % (d['variants'],)
            #if d.get('parameters_values'):
            #    name = name + ' - %s' % (d['parameters_values'],)
            return (d['id'], name)

        partner_id = context.get('partner_id', False)

        result = []
        for product in self.browse(cr, user, ids, context=context):
            sellers = filter(lambda x: x.name.id == partner_id, product.seller_ids)
            if sellers:
                for s in sellers:
                    mydict = {
                              'id': product.id,
                              'name': s.product_name or product.name,
                              'default_code': s.product_code or product.default_code,
                              #'variants': product.variants,
                              #'parameters_values': product.parameters_values,
                              }
                    result.append(_name_get(mydict))
            else:
                mydict = {
                          'id': product.id,
                          'name': product.name,
                          'default_code': product.default_code,
                          #'variants': product.variants,
                          #'parameters_values': product.parameters_values,
                          }
                result.append(_name_get(mydict))
        return result


    def write(self, cr, uid, ids, vals, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}
        res = super(product_product, self).write(cr, uid, ids, vals.copy(), context=context)

        ids_simple = self.search(cr, uid, [['id', 'in', ids], ['is_multi_variants', '=', False]], context=context)
       
        if not context.get('iamthechild', False) and ids_simple and ('name' in vals):
            if (not 'product_name' in vals) or (not vals['product_name']):
                vals_to_write={'product_name': vals['name']}
                ctx = context.copy()
                ctx['iamthechild'] = True
                self.write(cr, uid, ids, vals_to_write, context=ctx)

        return res

    def create(self, cr, uid, vals, context=None):
        #TAKE CARE for inherits objects openerp will create firstly the product_template and after the product_product
        # and so the duplicated fields (duplicated field = field which are on the template and on the variant) will be on the product_template and not on the product_product
        #Also when a product is created the duplicated field are empty for the product.product, this is why the field name can not be a required field
        #This should be fix in the orm in the futur
        ids = super(product_product, self).create(cr, uid, vals.copy(), context=context) #using vals.copy() if not the vals will be changed by calling the super method
        ####### write the value in the product_product
        if context is None:
            context = {}
        ctx = context.copy()
        ctx['iamthechild'] = True
        
        if (not 'product_name' in vals) or (not vals['product_name']):
            if 'name' in vals:
                vals_to_write={'product_name': vals['name']}
                self.write(cr, uid, ids, vals_to_write, context=ctx)

        return ids
    
    def parse(self, cr, uid, o, text, context=None):
        if not text:
            return ''
        vals = text.split('[_')
        description = ''
        for val in vals:
            if '_]' in val:
                sub_val = val.split('_]')
                try:
                    description += (safe_eval(sub_val[0], {'o' :o, 'context':context}) or '' ) + sub_val[1]
                except:
                    LOGGER.notifyChannel('product_variant_multi', netsvc.LOG_ERROR, "%s can't eval. Description is blank" % (sub_val[0]))
                    description += ''
            else:
                description += val
        return description


    def generate_product_code(self, cr, uid, product_obj, code_generator, context=None):
        '''I wrote this stupid function to be able to inherit it in a custom module !'''
        return self.parse(cr, uid, product_obj, code_generator, context=context)

    def build_product_code_and_properties(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        for product in self.browse(cr, uid, ids, context=context):
            new_default_code = self.generate_product_code(cr, uid, product, product.product_tmpl_id.code_generator, context=context)
            current_values = {
                'default_code': product.default_code,
                'track_production': product.track_production,
                'track_outgoing': product.track_outgoing,
                'track_incoming': product.track_incoming,
            }
            new_values = {
                'default_code': new_default_code,
                'track_production': product.product_tmpl_id.variant_track_production,
                'track_outgoing': product.product_tmpl_id.variant_track_outgoing,
                'track_incoming': product.product_tmpl_id.variant_track_incoming,
            }
            if new_values != current_values:
                self.write(cr, uid, product.id, new_values, context=context)
        return True

    def product_ids_variant_changed(self, cr, uid, ids, res, context=None):
        '''it's a hook for product_variant_multi advanced'''
        return True

    def generate_variant_name(self, cr, uid, product_id, context=None):
        '''Do the generation of the variant name in a dedicated function, so that we can
        inherit this function to hack the code generation'''
        if context is None:
            context = {}
        product = self.browse(cr, uid, product_id, context=context)
        model = product.variant_model_name
        r = map(lambda dim: [dim.dimension_id.sequence ,self.parse(cr, uid, dim, model, context=context)], product.dimension_value_ids)
        r.sort()
        r = [x[1] for x in r]
        new_variant_name = (product.variant_model_name_separator or '').join(r)
        return new_variant_name


    def build_variants_name(self, cr, uid, ids, context=None):
        for product in self.browse(cr, uid, ids, context=context):
            new_variant_name = self.generate_variant_name(cr, uid, product.id, context=context)
            if new_variant_name != product.variants:
                self.write(cr, uid, product.id, {'variants': new_variant_name}, context=context)
        return True

    def _check_dimension_values(self, cr, uid, ids): # TODO: check that all dimension_types of the product_template have a corresponding dimension_value ??
        for p in self.browse(cr, uid, ids, {}):
            buffer = []
            for value in p.dimension_value_ids:
                buffer.append(value.dimension_id)
            unique_set = set(buffer)
            if len(unique_set) != len(buffer):
                return False
        return True

    def compute_product_dimension_extra_price(self, cr, uid, product_id, product_price_extra=False, dim_price_margin=False, dim_price_extra=False, context=None):
        if context is None:
            context = {}
        dimension_extra = 0.0
        product = self.browse(cr, uid, product_id, context=context)
        for dim in product.dimension_value_ids:
            if product_price_extra and dim_price_margin and dim_price_extra:
                dimension_extra += safe_eval('product.' + product_price_extra, {'product': product}) * safe_eval('dim.' + dim_price_margin, {'dim': dim}) + safe_eval('dim.' + dim_price_extra, {'dim': dim})
            elif not product_price_extra and not dim_price_margin and dim_price_extra:
                dimension_extra += safe_eval('dim.' + dim_price_extra, {'dim': dim})
            elif product_price_extra and dim_price_margin and not dim_price_extra:
                dimension_extra += safe_eval('product.' + product_price_extra, {'product': product}) * safe_eval('dim.' + dim_price_margin, {'dim': dim})
            elif product_price_extra and not dim_price_margin and dim_price_extra:
                dimension_extra += safe_eval('product.' + product_price_extra, {'product': product}) + safe_eval('dim.' + dim_price_extra, {'dim': dim})

        if 'uom' in context:
            product_uom_obj = self.pool.get('product.uom')
            uom = product.uos_id or product.uom_id
            dimension_extra = product_uom_obj._compute_price(cr, uid,
                uom.id, dimension_extra, context['uom'])
        return dimension_extra


    def compute_dimension_extra_price(self, cr, uid, ids, result, product_price_extra=False, dim_price_margin=False, dim_price_extra=False, context=None):
        if context is None:
            context = {}
        for product in self.browse(cr, uid, ids, context=context):
            dimension_extra = self.compute_product_dimension_extra_price(cr, uid, product.id, product_price_extra=product_price_extra, dim_price_margin=dim_price_margin, dim_price_extra=dim_price_extra, context=context)
            result[product.id] += dimension_extra
        return result

    def price_get(self, cr, uid, ids, ptype='list_price', context=None):
        if context is None:
            context = {}
        result = super(product_product, self).price_get(cr, uid, ids, ptype, context=context)
        if ptype == 'list_price': #TODO check if the price_margin on the dimension is very usefull, maybe we will remove it
            result = self.compute_dimension_extra_price(cr, uid, ids, result, product_price_extra='price_extra', dim_price_margin='price_margin', dim_price_extra='price_extra', context=context)

        elif ptype == 'standard_price':
            result = self.compute_dimension_extra_price(cr, uid, ids, result, product_price_extra='cost_price_extra', dim_price_extra='cost_price_extra', context=context)
        return result

    def _product_lst_price(self, cr, uid, ids, name, arg, context=None):
        if context is None:
            context = {}
        result = super(product_product, self)._product_lst_price(cr, uid, ids, name, arg, context=context)
        result = self.compute_dimension_extra_price(cr, uid, ids, result, product_price_extra='price_extra', dim_price_margin='price_margin', dim_price_extra='price_extra', context=context)
        return result


    def copy(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}
        default = default.copy()
        default.update({'variant_ids':False,})
        return super(product_product, self).copy(cr, uid, id, default, context)

    def _product_compute_weight_volume(self, cr, uid, ids, fields, arg, context=None):
        result = {}
        # print 'compute', ids, fields, context
        for product in self.browse(cr, uid, ids, context=context):
            result[product.id]={}
            result[product.id]['total_weight'] =  product.weight + product.additional_weight
            result[product.id]['total_weight_net'] =  product.weight_net + product.additional_weight_net
            result[product.id]['total_volume'] = product.volume + product.additional_volume
        return result
    
    def _get_parameters_values(self, cr, uid, ids, fields, arg, context=None):
        products = self.pool.get('product.product').browse(cr, uid, ids)
        ret = {}
        for product in products:
            if not product.is_multi_variants:
                ret[product.id] = ''
            else:
                value = ''
                for param in product.dimension_value_ids:
                    value += ' %s - %s' % (param.dimension_id.name, param.option_id.name)
                ret[product.id] = value[1:]
        return ret

    def _register_uom_rel(self, cr, uid, ids, name, arg, context=None):
        products = self.browse(cr, uid, ids, context=context)
        res = {}
        for p in products:
            rule = p.register_uom_rule
            
            if rule and len(rule):
                result = 0.00

                rule_list = re.split('\+|\-|\*|\/', rule)
                delim_list = []
                for i in rule:
                    if i in ('+', '-', '*', '/'):
                        delim_list.append(i)
                if len(delim_list)+1 == len(rule_list):
                    for value in p.dimension_value_ids:
                        dim_description = value.dimension_id.description
                        option_value = value.option_id.name
                        rule_list = [(option_value if item == dim_description else item) for item in rule_list]
                    
                    try:
                        rule_list = [str(float(item)) for item in rule_list]
                    except Exception, e:
                        result = 0.00
                        print 'Product "%s" - convert to register_uom error - %s' % (p.name, str(rule))
                    else:
                        rule = rule_list[0]
                        for i in range(1, len(rule_list)):
                            rule += delim_list[i-1] + rule_list[i]
                        try:
                            result = round(eval(rule), 3)
                            #print 'Eval success: %s - %s' % (rule, str(result))
                        except Exception, e:
                            result = 0.00
                            print 'Eval error - %s' % e.message
                else:
                    result = 0.00
            else:
                result = 0.00
            
            res[p.id] = result
        
        return res
    
    def _register_uom_qty(self, cr, uid, ids, name, arg, context=None):
        products = self.browse(cr, uid, ids, context=context)
        res = {}
        for p in products:
            if name == 'register_uom_qty':
                res[p.id] = p.register_uom_rel * p.qty_available
            elif name == 'register_uom_virtual':
                res[p.id] = p.register_uom_rel * p.virtual_available
            else:
                res[p.id] = 0.00
        return res
        

    _columns = {
        'product_name': fields.char('Name', size=128, readonly=False),
        # Fictive field for multi fields - don't change this
        'multi': fields.dummy(string='Multi fields'),
        'params': fields.dummy(string='Params fields'),
        
        'dimension_value_ids': fields.many2many('product.variant.dimension.value', 'product_product_dimension_rel', 'product_id','dimension_id', 'Dimensions', domain="[('product_tmpl_id','=',product_tmpl_id)]"),
        'cost_price_extra' : fields.float('Purchase Extra Cost', digits_compute=dp.get_precision('Purchase Price')),
        'lst_price' : fields.function(_product_lst_price, method=True, type='float', string='List Price', digits_compute=dp.get_precision('Sale Price')),
        #the way the weight are implemented are not clean at all, we should redesign the module product form the addons in order to get something correclty.
        #indeed some field of the template have to be overwrited like weight, name, weight_net, volume.
        #in order to have a consitent api we should use the same field for getting the weight, now we have to use "weight" or "total_weight" not clean at all with external syncronization
        'total_weight': fields.function(_product_compute_weight_volume, method=True, type='float', string='Gross weight', help="The gross weight in Kg.", multi='weight_volume'),
        'total_weight_net': fields.function(_product_compute_weight_volume, method=True, type='float', string='Net weight', help="The net weight in Kg.", multi='weight_volume'),
        'total_volume':  fields.function(_product_compute_weight_volume, method=True, type='float', string='Volume', help="The volume in m3.", multi='weight_volume'),
        'additional_weight': fields.float('Additional Gross weight', help="The additional gross weight in Kg."),
        'additional_weight_net': fields.float('Additional Net weight', help="The additional net weight in Kg."),
        'additional_volume': fields.float('Additional Volume', help="The additional volume in Kg."),
        'parameters_values': fields.function(_get_parameters_values, method=True, type='char', string='Значения характеристик', help="Значения параметров продукта."),
        # Fields for register uom
        'register_uom_rel': fields.function(_register_uom_rel, method=True, type='float', string=u'Uoms, %', help=u'Отношение учетных ед.изм. к дефолтным'),
        'register_uom_qty': fields.function(_register_uom_qty, method=True, type='float', string='Учетное кол-во', help=u'Аналог qty_available для учетной ед. изм.'),
        'register_uom_virtual': fields.function(_register_uom_qty, method=True, type='float', string='Учетное виртуальное кол-во', help=u'Аналог virtual_available для учетной ед. изм.')
    }
    
    _constraints = [ (_check_dimension_values, 'Several dimension values for the same dimension type', ['dimension_value_ids']),]

    def search(self, cr, uid, args, offset=0, limit=None, order=None, context=None, count=False):
        # Variant fields
        multi_fields = {}
        
        inherits=[self, ]
        if self._inherits:
            for inh in self._inherits.keys():
                inherits.append(self.pool.get(inh))
        
        #Get fields from own object (product.product) and it's _inherits
        exists_fields=['id', ]
        for column in args:
            if column[0] == 'product_tmpl_id':
                product_tmpl_id=column[2]
            for inh in inherits:
                if (column[0] in inh._columns) and (column[0] not in exists_fields):
                    exists_fields.append(column[0])
        ind_del=[]
        for item in args:
            if (item[0] not in exists_fields) and (not isinstance(item, str)):
                multi_fields[item[0].replace('product_tmpl_id_', '')]=item
                ind_del.append(item)
        for i in ind_del:
            args.remove(i)
    
        # Search without variant fields
        if multi_fields:
            old_limit=copy(limit)
            limit=None
            old_offset=copy(offset)
            offset=0
        result=super(product_product, self).search(cr, uid, args, offset, limit, order, context, count)

        # If we need to additional filter with variant fields
        if multi_fields:
            if isinstance(result, list):
                query="""
                        SELECT id FROM product_variant_dimension_value
                        WHERE product_tmpl_id=%d AND (
                    """ % (product_tmpl_id)
                for type, value in multi_fields.items():
                    query += ' (dimension_id=%s AND option_id=%s) OR' % (type, value[2])
                query=query[:-2] + ')'
            cr.execute(query)
            ids_rel=cr.fetchall()
            tmp=[i[0] for i in ids_rel]
            ids_rel=tmp

            products=self.read(cr, uid, result, ['dimension_value_ids'], context)
            result=[]
            for product in products:
                flag=False
                for id_rel in ids_rel:
                    if id_rel not in product['dimension_value_ids']:
                        flag=True
                if not flag:
                    result.append(product['id'])
            result=result[old_offset:old_offset+old_limit] # Cut results for limit
        
        return result
    

    def multi_search_one(self, cr, uid, template_id, dimensions, context=None):
        """Return list of products's IDs, which have choosen dimensions"""
        
        product_ids = self.search(cr, uid, [('product_tmpl_id', '=', template_id)])

        if not len(dimensions):
            return product_ids

        query="""
                    SELECT id FROM product_variant_dimension_value
                    WHERE product_tmpl_id=%d AND (
                """ % (template_id)
        
        for type, value in dimensions.items():
            query += ' (dimension_id=%s AND option_id=%s) OR' % (type, value)
        query=query[:-2] + ')'
        cr.execute(query)
        ids_rel=cr.fetchall()
        tmp=[i[0] for i in ids_rel]
        ids_rel=tmp
        
        products=self.read(cr, uid, product_ids, ['dimension_value_ids'], context)
        result=[]
        for product in products:
            flag=False
            for id_rel in ids_rel:
                if id_rel not in product['dimension_value_ids']:
                    flag=True
            if not flag:
                result.append(product['id'])
        
        return result
        

    def fields_view_get(self, cr, uid, view_id, view_type='form', context=None, toolbar=False, submenu=False):
        fields = super(product_product, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        # If product.product's search view with product_tmpl_id
        if ('template_id' in context) and context['template_id'] and view_type == 'search':
            # Get all variants for current template
            tmpl_id=context['template_id']
            fields['selected'] = {}
            fields['selected']['product_tmpl_id']=tmpl_id

            query="""
                SELECT dv.dimension_id, dv.option_id, dt.name as type_name, dop.name as option_name, dt.sequence
                FROM product_variant_dimension_value as dv
                LEFT JOIN product_variant_dimension_type as dt ON dt.id=dv.dimension_id
                LEFT JOIN product_variant_dimension_option as dop ON dop.id=dv.option_id
                WHERE dv.product_tmpl_id=%s
            """ % tmpl_id
            cr.execute(query)
            multi_fields=cr.fetchall()
                        
            multi_types = {}
            multi_types_str = ''
            # Add variant fields
            for row in multi_fields:
                # 0 - type_id, 1 - option_id, 2 - type_name, 3 - option_name, 4 - sequence
                field_name='product_tmpl_id_'+str(row[0])
                if field_name not in multi_types:
                    multi_types[field_name]={
                        'context': {},
                        'domain': [],
                        'relation': 'product.variant.dimension.option',
                        'required': False,
                        'selectable': True,
                        'selection': [(row[1], row[3])],
                        'string': row[2],
                        'type': 'many2one',
                        'views': {},
                        'sequence': row[4],
                    }
                    multi_types_str+='<field name="%s" widget="selection" />' % field_name 
                else:
                    multi_types[field_name]['selection'].append((row[1], row[3]))
            
            # Add dimensions without options
            if 'hide_empty_params' not in context or not context['hide_empty_params']:
                query = """
                SELECT dt.id, dt.name, dt.sequence
                FROM product_template_dimension_rel dr
                LEFT JOIN product_variant_dimension_type dt ON dt.id = dr.dimension_id
                WHERE dr.template_id = %s
                """ % tmpl_id
                cr.execute(query)
                empty_dims = cr.fetchall()
                # 0 - dim_id, 1 - dim_name, 2 - dim.sequence
                for dim in empty_dims:
                    # If this dimension already in list
                    ex_flag = False
                    for exists_dim in multi_fields:
                        if dim[0] == exists_dim[0]:
                            ex_flag = True
                            break
                    if not ex_flag:
                        multi_types['product_tmpl_id_'+str(dim[0])] = {
                            'context': {},
                            'domain': [],
                            'relation': 'product.variant.dimension.option',
                            'required': False,
                            'selectable': True,
                            'selection': [],
                            'string': dim[1],
                            'type': 'many2one',
                            'views': {},
                            'sequence': dim[2],
                        }
                        multi_types_str+='<field name="%s" widget="selection" />' % 'product_tmpl_id_'+str(dim[0])
            
            for key, val in multi_types.items():
                fields['fields'][key] = val
            fields['arch']=re.sub('<field\s+name=(\'|\")multi(\'|\")[^>]+>', multi_types_str, fields['arch'].decode('utf-8'))
            
        elif view_type == 'tree':
            # Add columns with product's parameters
            type_obj = self.pool.get('product.variant.dimension.type')
            types = type_obj.search(cr, uid, [('show_in_tree', '=', True)])
            types = type_obj.browse(cr, uid, types)
            arch = ''
            for type in types:
                fields['fields'].update({type.description: {
                                                     'select': True,
                                                     'selectable': True,
                                                     'size': 64,
                                                     'string': type.name,
                                                     'type': 'char',
                                                     }})
                arch += '<field name="%s" />' % type.description
            
            fields['arch']=re.sub('<field\s+name=(\'|\")params(\'|\")[^>]+>', arch, fields['arch'].decode('utf-8'))
            fields['arch']=re.sub('<field\s+name=(\'|\")multi(\'|\")[^>]+>', '', fields['arch'])
        else:
            fields['arch']=re.sub('<field\s+name=(\'|\")multi(\'|\")[^>]+>', '', fields['arch'].decode('utf-8'))
            fields['arch']=re.sub('<field\s+name=(\'|\")params(\'|\")[^>]+>', '', fields['arch'])        
        
        return fields
        
    def read(self, cr, uid, ids, fields=None, context=None, load="_classic_read"):  
        if isinstance(ids, int) or isinstance(ids, long):
            ids = [ids]
        time1 = time.time()
        ff = []
        for i, item in enumerate(ids):
            if not item:
                ff.append(i)
        ff.reverse()
        for i in ff:
            del(ids[i])                
        ret = super(product_product, self).read(cr, uid, ids, fields=fields, context=context, load=load)

        type_obj = self.pool.get('product.variant.dimension.type')
        types = type_obj.search(cr, uid, [('show_in_tree', '=', True)])
        
        param_fields = []
        if fields:
            for type in type_obj.browse(cr, uid, types):
                if type.description in fields:
                    param_fields.append(type.description)
                  
        if param_fields and ids:
            query = """SELECT dr.product_id, dt.description, dop.name
            FROM product_product_dimension_rel dr
            LEFT JOIN product_variant_dimension_value dv on dr.dimension_id = dv.id
            LEFT JOIN product_variant_dimension_type dt on dv.dimension_id = dt.id
            LEFT JOIN product_variant_dimension_option dop on dv.option_id = dop.id
            WHERE dr.product_id in %s
            """

            cr.execute(query, (tuple(ids),))
            q_res = cr.fetchall()
            products_params = {}
            for product_id, dim, opt in q_res:
                if product_id not in products_params:
                    products_params[product_id] = {}
                products_params[product_id].update({dim: opt})
            
            for product in self.pool.get('product.product').read(cr, uid, ids, ['id']):
                for i, item in enumerate(ret):
                    if item['id'] == product['id']:
                        ind = i
                        break
                    
                if product['id'] in products_params:
                    for dim, opt in products_params[product['id']].items():
                        if dim in param_fields:
                            ret[ind].update({dim: opt})
                
        time2 = time.time()
        if (time2 - time1) > 1:
            print "Time for showing parameters - %s" % round(time2-time1)
        return ret

    def read_group(self, cr, uid, domain, fields=None, group_by_fields=None, p1=False, p2=False, context=None, sort=False):
        dims = self.pool.get('product.variant.dimension.type').search(cr, uid, [])
        for dim in self.pool.get('product.variant.dimension.type').browse(cr, uid, dims):
            if dim.description in fields:
                del(fields[fields.index(dim.description)])
        ret = super(product_product, self).read_group(cr, uid, domain, fields, group_by_fields, p1, p2, context, sort)
        return ret
        
product_product()


