from bpy.types import (
    Node,
    NodeGroupInput,
    NodeGroupOutput,
    NodeSocket,
    NodeSocketBool,
    NodeSocketColor,
    NodeSocketFloat,
    NodeSocketInt,
    NodeSocketShader,
    NodeSocketVector,
    ShaderNodeAddShader,
    ShaderNodeBevel,
    ShaderNodeBrightContrast,
    ShaderNodeBsdfAnisotropic,
    ShaderNodeBsdfDiffuse,
    ShaderNodeBsdfPrincipled,
    ShaderNodeBsdfTranslucent,
    ShaderNodeBsdfTransparent,
    ShaderNodeBump,
    ShaderNodeCombineXYZ,
    ShaderNodeEmission,
    ShaderNodeGroup,
    ShaderNodeLayerWeight,
    ShaderNodeMapping,
    ShaderNodeMapRange,
    ShaderNodeMath,
    ShaderNodeMix,
    ShaderNodeMixShader,
    ShaderNodeNewGeometry,
    ShaderNodeNormalMap,
    ShaderNodeObjectInfo,
    ShaderNodeRGB,
    ShaderNodeRGBCurve,
    ShaderNodeSeparateXYZ,
    ShaderNodeTexCoord,
    ShaderNodeTexImage,
    ShaderNodeTexNoise,
    ShaderNodeTexVoronoi,
    ShaderNodeUVMap,
    ShaderNodeValToRGB,
    ShaderNodeValue,
    ShaderNodeVectorMath,
    ShaderNodeVectorTransform,
    ShaderNodeVolumeAbsorption,
)

node_types = {
    'value': ShaderNodeValue,
    'color': ShaderNodeRGB,
    'vector': ShaderNodeRGB, # TODO: Custom node group with a three-number panel or whatever

    'translucent_bsdf': ShaderNodeBsdfTranslucent,
    'principled_bsdf': ShaderNodeBsdfPrincipled,
    'transparent_bsdf': ShaderNodeBsdfTransparent,

    'mix_value': ShaderNodeMix,
    'mix': ShaderNodeMix,
    'mix_closure': ShaderNodeMixShader,

    # In modern blender, mix can act as switch when the input is boolean
    'switch_float': ShaderNodeMix,
    'switch_closure': ShaderNodeMixShader, 
    'glossy_bsdf': ShaderNodeBsdfAnisotropic, # unsure

    'noise_texture': ShaderNodeTexNoise,
    'image_texture': ShaderNodeTexImage,
    'voronoi_texture': ShaderNodeTexVoronoi,

    'group_input': NodeGroupInput,
    'group_output': NodeGroupOutput,
    'group': ShaderNodeGroup,

    'separate_xyz': ShaderNodeSeparateXYZ,
    'combine_xyz': ShaderNodeCombineXYZ,

    'add_closure': ShaderNodeAddShader,
    'emission': ShaderNodeEmission,
    'texture_coordinate': ShaderNodeTexCoord,
    'vector_transform': ShaderNodeVectorTransform,
    'bump': ShaderNodeBump,
    'rounding_edge_normal': ShaderNodeBevel,
    'math': ShaderNodeMath,
    'mapping': ShaderNodeMapping,
    'map_range': ShaderNodeMapRange,
    'rgb_ramp': ShaderNodeValToRGB,
    'object_info': ShaderNodeObjectInfo,
    'diffuse_bsdf': ShaderNodeBsdfDiffuse,
    'normal_map': ShaderNodeNormalMap,
    'vector_math': ShaderNodeVectorMath,
    'brightness_contrast': ShaderNodeBrightContrast,
    'uvmap': ShaderNodeUVMap,
    'rgb_curves': ShaderNodeRGBCurve,
    'geometry': ShaderNodeNewGeometry,
    'absorption_volume': ShaderNodeVolumeAbsorption,
    'layer_weight': ShaderNodeLayerWeight,
}

socket_types: dict[str, type[NodeSocket]] = {
    'color': NodeSocketColor,
    'closure': NodeSocketShader,
    'vector': NodeSocketVector,
    'float': NodeSocketFloat,
    'int': NodeSocketInt,
    'boolean': NodeSocketBool,
}

passthroughs = {
    'Levels': NodeSocketInt,
    'MinColorRatio': NodeSocketFloat,
    'MaxColorRatio': NodeSocketFloat,
    'enable': NodeSocketBool,
}

custom_node_groups = {
    'uv_degradation': 'UV Degradation',
    'project_to_axis_plane': 'Project to Axis Planes',
}

input_aliases: dict[type[Node], dict[str, str | int]] = {
    ShaderNodeMapRange: { 'Value': 'Result' },
    ShaderNodeBevel: { 'Size': 'Radius' },
    ShaderNodeMath: { 'Value1': 0, 'Value2': 1 },
    ShaderNodeMix: { 'Fac': 'Factor' },
    ShaderNodeVectorMath: { 'Vector1': 0, 'Vector2': 1 },
    ShaderNodeAddShader: { 'Shader1': 0, 'Shader2': 1 },
    ShaderNodeMixShader: { 'Shader1': 1, 'Shader2': 2 },
    ShaderNodeMix: {
        'Fac': 0,
        # <switch_float>
        'ValueDisable': 2,
        'ValueEnable': 3,
        # <mix_value>
        'Value1': 2,
        'Value2': 3,
        # <mix>
        'Color1': 6,
        'Color2': 7,
    },
    ShaderNodeBsdfPrincipled: {
        'Subsurface': 'Subsurface Weight',
        'Clearcoat': 'Coat Weight',
        'ClearcoatRoughness': 'Coat Roughness',
        'Clearcoat Roughness': 'Coat Roughness',
        'ClearcoatNormal': 'Coat Normal',
        'Clearcoat Normal': 'Coat Normal',
        'Transmission': 'Transmission Weight',
        'Sheen': 'Sheen Weight',
        'SheenTint': 'Sheen Tint',
        'Specular': 'Specular IOR Level',
        'SpecularTint': 'Specular Tint',
        'AnisotropicRotation': 'Anisotropic Rotation',
        'SubsurfaceRadius': 'Subsurface Radius',

        # # Not sure these are accurate.
        'TransmissionRoughness': 'Roughness',
        'Transmission Roughness': 'Roughness',
        'SubsurfaceColor': 'Subsurface Radius',
        'BaseColor': 'Base Color',
        'Color': 'Base Color',
    }
}

output_aliases: dict[type[Node], dict[str, str | int]] = {
    ShaderNodeMix: {
        'Value': 'Result',
        'ValueOut': 'Result',
        'Color': 'Result',
    },
    ShaderNodeTexVoronoi: {
        'Fac': 'Distance', # TODO: Or 'Position'?
    },
}
