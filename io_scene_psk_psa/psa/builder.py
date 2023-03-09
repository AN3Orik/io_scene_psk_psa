from typing import Optional

from bpy.types import Armature, Bone, Action

from .data import *
from ..helpers import *


class PsaExportSequence:
    class NlaState:
        def __init__(self):
            self.action: Optional[Action] = None
            self.frame_start: int = 0
            self.frame_end: int = 0

    def __init__(self):
        self.name: str = ''
        self.nla_state: PsaExportSequence.NlaState = PsaExportSequence.NlaState()
        self.fps: float = 30.0


class PsaBuildOptions:
    def __init__(self):
        self.animation_data: AnimData = None
        self.sequences: List[PsaExportSequence] = []
        self.bone_filter_mode = 'ALL'
        self.bone_group_indices: List[int] = []
        self.should_use_original_sequence_names = False
        self.should_ignore_bone_name_restrictions = False
        self.sequence_name_prefix = ''
        self.sequence_name_suffix = ''
        self.root_motion = False


def build_psa(context: bpy.types.Context, options: PsaBuildOptions) -> Psa:
    active_object = context.view_layer.objects.active

    psa = Psa()

    armature_object = active_object
    armature_data = typing.cast(Armature, armature_object.data)
    bones: List[Bone] = list(iter(armature_data.bones))

    # The order of the armature bones and the pose bones is not guaranteed to be the same.
    # As a result, we need to reconstruct the list of pose bones in the same order as the
    # armature bones.
    bone_names = [x.name for x in bones]
    pose_bones = [(bone_names.index(bone.name), bone) for bone in armature_object.pose.bones]
    pose_bones.sort(key=lambda x: x[0])
    pose_bones = [x[1] for x in pose_bones]

    # Get a list of all the bone indices and instigator bones for the bone filter settings.
    export_bone_names = get_export_bone_names(armature_object, options.bone_filter_mode, options.bone_group_indices)
    bone_indices = [bone_names.index(x) for x in export_bone_names]

    # Make the bone lists contain only the bones that are going to be exported.
    bones = [bones[bone_index] for bone_index in bone_indices]
    pose_bones = [pose_bones[bone_index] for bone_index in bone_indices]

    # No bones are going to be exported.
    if len(bones) == 0:
        raise RuntimeError('No bones available for export')

    # Check that all bone names are valid.
    if not options.should_ignore_bone_name_restrictions:
        check_bone_names(map(lambda bone: bone.name, bones))

    # Build list of PSA bones.
    for bone in bones:
        psa_bone = Psa.Bone()
        psa_bone.name = bytes(bone.name, encoding='windows-1252')

        try:
            parent_index = bones.index(bone.parent)
            psa_bone.parent_index = parent_index
            psa.bones[parent_index].children_count += 1
        except ValueError:
            psa_bone.parent_index = -1

        if bone.parent is not None:
            rotation = bone.matrix.to_quaternion().conjugated()
            inverse_parent_rotation = bone.parent.matrix.to_quaternion().inverted()
            parent_head = inverse_parent_rotation @ bone.parent.head
            parent_tail = inverse_parent_rotation @ bone.parent.tail
            location = (parent_tail - parent_head) + bone.head
        else:
            armature_local_matrix = armature_object.matrix_local
            location = armature_local_matrix @ bone.head
            bone_rotation = bone.matrix.to_quaternion().conjugated()
            local_rotation = armature_local_matrix.to_3x3().to_quaternion().conjugated()
            rotation = bone_rotation @ local_rotation
            rotation.conjugate()

        psa_bone.location.x = location.x
        psa_bone.location.y = location.y
        psa_bone.location.z = location.z

        psa_bone.rotation.x = rotation.x
        psa_bone.rotation.y = rotation.y
        psa_bone.rotation.z = rotation.z
        psa_bone.rotation.w = rotation.w

        psa.bones.append(psa_bone)

    # Add prefixes and suffices to the names of the export sequences and strip whitespace.
    for export_sequence in options.sequences:
        export_sequence.name = f'{options.sequence_name_prefix}{export_sequence.name}{options.sequence_name_suffix}'
        export_sequence.name = export_sequence.name.strip()

    # Save the current action and frame so that we can restore the state once we are done.
    saved_frame_current = context.scene.frame_current
    saved_action = options.animation_data.action

    # Now build the PSA sequences.
    # We actually alter the timeline frame and simply record the resultant pose bone matrices.
    frame_start_index = 0

    for export_sequence in options.sequences:
        # Link the action to the animation data and update view layer.
        options.animation_data.action = export_sequence.nla_state.action
        context.view_layer.update()

        frame_min = export_sequence.nla_state.frame_min
        frame_max = export_sequence.nla_state.frame_max
        frame_count = frame_max - frame_min + 1

        psa_sequence = Psa.Sequence()
        psa_sequence.name = bytes(export_sequence.name, encoding='windows-1252')
        psa_sequence.frame_count = frame_count
        psa_sequence.frame_start_index = frame_start_index
        psa_sequence.fps = export_sequence.fps

        for frame in range(frame_count):
            context.scene.frame_set(frame_min + frame)

            for pose_bone in pose_bones:
                key = Psa.Key()

                if pose_bone.parent is not None:
                    pose_bone_matrix = pose_bone.matrix
                    pose_bone_parent_matrix = pose_bone.parent.matrix
                    pose_bone_matrix = pose_bone_parent_matrix.inverted() @ pose_bone_matrix
                else:
                    if options.root_motion:
                        # Export root motion
                        pose_bone_matrix = armature_object.matrix_world @ pose_bone.matrix
                    else:
                        pose_bone_matrix = pose_bone.matrix

                location = pose_bone_matrix.to_translation()
                rotation = pose_bone_matrix.to_quaternion().normalized()

                if pose_bone.parent is not None:
                    rotation.conjugate()

                key.location.x = location.x
                key.location.y = location.y
                key.location.z = location.z
                key.rotation.x = rotation.x
                key.rotation.y = rotation.y
                key.rotation.z = rotation.z
                key.rotation.w = rotation.w
                key.time = 1.0 / psa_sequence.fps

                psa.keys.append(key)

            psa_sequence.bone_count = len(pose_bones)
            psa_sequence.track_time = frame_count

        frame_start_index += frame_count

        psa.sequences[export_sequence.name] = psa_sequence

    # Restore the previous action & frame.
    options.animation_data.action = saved_action
    context.scene.frame_set(saved_frame_current)

    return psa
